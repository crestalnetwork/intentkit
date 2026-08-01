"""Tools for reading webpage content as markdown via different providers."""

import asyncio
import logging
import re
import time
from typing import Annotated, override

import httpx
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_tools.base import SystemTool
from intentkit.tools.http.base import validate_url

logger = logging.getLogger(__name__)

CLEAN_CONTENT_PROMPT = """\
You are a content extractor. Given raw markdown converted from a webpage, \
extract only the meaningful, readable content. Remove:
- Navigation menus, headers, footers, sidebars
- Cookie notices, ads, promotional banners
- Repetitive links, social media buttons
- Any boilerplate or non-content elements

Return ONLY the clean, readable main content in markdown format. \
Do not add any commentary or explanation."""


_MAX_CONTENT_CHARS = 50000
_NO_CONTENT = "The URL returned no content."

# Content types that are already machine-readable text: returned directly
# without browser rendering or LLM cleaning. Deliberately excludes HTML/XHTML
# (those need rendering) and generic XML (ambiguous).
_DIRECT_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/rss+xml",
        "application/atom+xml",
    }
)
_DIRECT_FETCH_TIMEOUT = 20.0
# Download cap for direct fetches; UTF-8 needs at most 4 bytes per char, so
# this always covers the _MAX_CONTENT_CHARS the tool can return.
_DIRECT_MAX_BYTES = 4 * _MAX_CONTENT_CHARS

# Cloudflare Browser Rendering rate limiting. The free plan allows only
# 1 REST request every 10 seconds per account, so calls are spaced out and
# 429s are retried after the window clears. The pacer is per-process while
# the quota is per account; the retry loop absorbs contention from other
# processes (api server / autonomous runner / scheduler).
_CF_TIMEOUT = 60.0
_CF_MIN_INTERVAL = 10.0
_CF_MAX_ATTEMPTS = 4
_CF_RETRY_BASE_DELAY = 10.0
_CF_MAX_RETRY_DELAY = 120.0

_cf_pacer_lock = asyncio.Lock()
_cf_next_slot = 0.0  # time.monotonic() timestamp of the next free slot


async def _reserve_cloudflare_slot() -> None:
    """Space Cloudflare calls at least _CF_MIN_INTERVAL apart, process-wide.

    Each caller reserves the next free slot under the lock, then sleeps
    outside it, so concurrent callers queue up evenly instead of bursting.
    """
    global _cf_next_slot
    async with _cf_pacer_lock:
        now = time.monotonic()
        wait = _cf_next_slot - now
        _cf_next_slot = max(_cf_next_slot, now) + _CF_MIN_INTERVAL
    if wait > 0:
        await asyncio.sleep(wait)


async def _hold_cloudflare_slots(delay: float) -> None:
    """Push the shared slot out after a 429 so all callers back off together.

    The waiting itself happens in the caller's next _reserve_cloudflare_slot,
    so the hold and the pacing spacing compose as a max, not a sum.
    """
    global _cf_next_slot
    async with _cf_pacer_lock:
        _cf_next_slot = max(_cf_next_slot, time.monotonic() + delay)


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    """Delay before retrying a 429, honoring a seconds-valued Retry-After.

    Cloudflare sends Retry-After in seconds; the RFC 7231 HTTP-date form
    (and any other unparsable value) falls back to exponential backoff.
    """
    if retry_after:
        try:
            return min(float(retry_after), _CF_MAX_RETRY_DELAY)
        except ValueError:
            pass
    return min(_CF_RETRY_BASE_DELAY * (2**attempt), _CF_MAX_RETRY_DELAY)


async def _validate_request_url(request: httpx.Request) -> None:
    """httpx request hook: re-check every hop so a redirect chain cannot
    escape the SSRF guard applied to the original URL."""
    validate_url(str(request.url))


def _is_direct_content_type(content_type: str) -> bool:
    """True when the body is machine-readable text needing no rendering."""
    return content_type in _DIRECT_CONTENT_TYPES or content_type.endswith("+json")


def _normalize_whitespace(text: str) -> str:
    """Collapse redundant whitespace in markdown content."""
    cleaned = re.sub(r" {2,}", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _truncate(text: str) -> str:
    """Truncate content that exceeds the maximum length."""
    if len(text) > _MAX_CONTENT_CHARS:
        return text[:_MAX_CONTENT_CHARS] + "\n\n... (content truncated)"
    return text


class ReadWebpageInput(BaseModel):
    """Input schema for reading a webpage."""

    url: str = Field(..., description="The URL of the webpage to read")


class ReadWebpageCloudflareTool(SystemTool):
    """Tool for reading webpage content as markdown via Cloudflare.

    Plain-text resources (JSON APIs, markdown files, feeds) are fetched
    directly and returned as-is. Webpages go through the Cloudflare Browser
    Rendering REST API to be converted to markdown, then cleaned with an LLM.
    """

    name: str = "read_webpage_cloudflare"
    description: str = (
        "Read a webpage or API endpoint and return its content. "
        "JSON and other plain-text responses are returned as-is; webpages are "
        "rendered via Cloudflare Browser Rendering and converted to markdown. "
        "Useful when you need to read and understand the content of a specific URL."
    )
    args_schema: ArgsSchema | None = ReadWebpageInput

    @override
    async def _arun(
        self,
        url: str,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
    ) -> str:
        """Read a webpage and return its content as markdown.

        Args:
            url: The URL of the webpage to read.
            tool_call_id: Injected by LangChain runtime.

        Returns:
            The webpage content converted to markdown.
        """
        try:
            validate_url(url)

            # JSON APIs and other plain-text resources don't need browser
            # rendering or LLM cleaning; fetch them directly to save the
            # tight Cloudflare rate-limit budget.
            direct = await self._try_direct_fetch(url)
            if direct is not None:
                return _truncate(direct) if direct.strip() else _NO_CONTENT

            from intentkit.config.config import config

            account_id = config.cloudflare_account_id
            api_token = config.cloudflare_api_token
            if not account_id or not api_token:
                raise ToolException(
                    "Cloudflare Browser Rendering is not configured. "
                    "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
                )

            # Fetch webpage as markdown via Cloudflare
            raw_markdown = await self._fetch_markdown(account_id, api_token, url)
            if not raw_markdown:
                return _NO_CONTENT

            cleaned = _normalize_whitespace(raw_markdown)

            # Clean content with LLM
            cleaned = await self._clean_with_llm(cleaned, tool_call_id)

            return _truncate(cleaned)

        except ToolException:
            raise
        except Exception as e:
            logger.exception("read_webpage failed")
            raise ToolException(f"Failed to read webpage: {e}") from e

    async def _try_direct_fetch(self, url: str) -> str | None:
        """Fetch the URL directly and return its body if it is plain text.

        The decision is made on the response headers, so bodies of webpages
        (or anything else that needs browser rendering) are never downloaded;
        direct bodies are read up to _DIRECT_MAX_BYTES. Redirects are
        followed, with every hop re-checked against the SSRF guard by the
        request hook. Returns None on any error to fall back to Cloudflare.
        """
        try:
            async with (
                httpx.AsyncClient(
                    timeout=_DIRECT_FETCH_TIMEOUT,
                    follow_redirects=True,
                    max_redirects=5,
                    event_hooks={"request": [_validate_request_url]},
                ) as client,
                client.stream("GET", url) as response,
            ):
                if response.status_code != 200:
                    return None
                content_type = (
                    response.headers.get("content-type", "")
                    .split(";")[0]
                    .strip()
                    .lower()
                )
                if not _is_direct_content_type(content_type):
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) >= _DIRECT_MAX_BYTES:
                        break
                return bytes(body[:_DIRECT_MAX_BYTES]).decode(
                    response.encoding or "utf-8", errors="replace"
                )
        except Exception as e:
            logger.debug("direct fetch failed for %s: %s", url, e)
            return None

    async def _fetch_markdown(self, account_id: str, api_token: str, url: str) -> str:
        """Fetch a URL and convert to markdown via Cloudflare Browser Rendering.

        Calls are paced process-wide and retried with backoff on 429, since
        the Cloudflare REST API rate limit is easily hit by bursts of reads.
        """
        api_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/markdown"

        async with httpx.AsyncClient(timeout=_CF_TIMEOUT) as client:
            attempt = 0
            while True:
                await _reserve_cloudflare_slot()
                response = await client.post(
                    api_url,
                    json={
                        "url": url,
                        "rejectRequestPattern": [".*\\.(css|ico|svg|woff2?|ttf|eot)$"],
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_token}",
                    },
                )
                if response.status_code != 429:
                    break
                attempt += 1
                if attempt >= _CF_MAX_ATTEMPTS:
                    raise ToolException(
                        "Cloudflare Browser Rendering is rate limited right now. "
                        "Wait a while before reading more webpages."
                    )
                delay = _retry_delay(response.headers.get("retry-after"), attempt - 1)
                logger.info(
                    "Cloudflare rate limited, retrying in ~%.0fs (attempt %d/%d)",
                    delay,
                    attempt,
                    _CF_MAX_ATTEMPTS,
                )
                await _hold_cloudflare_slots(delay)

        if response.status_code != 200:
            raise ToolException(
                f"Cloudflare API returned status {response.status_code}: {response.text}"
            )

        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            raise ToolException(f"Cloudflare API error: {errors}")

        return data.get("result", "")

    async def _clean_with_llm(self, content: str, tool_call_id: str | None) -> str:
        """Use a long-context LLM to extract readable content from raw markdown."""
        from intentkit.models.llm import create_llm_model
        from intentkit.models.llm_picker import pick_long_context_model

        model_id = pick_long_context_model()
        # Boilerplate stripping needs no reasoning; "none" clamps to the
        # weakest level the picked model supports.
        llm_model = await create_llm_model(model_id, reasoning_effort="none")
        llm = await llm_model.create_instance()

        response = await llm.ainvoke(
            [
                {"role": "system", "content": CLEAN_CONTENT_PROMPT},
                {"role": "user", "content": content},
            ]
        )

        await self._bill_internal_llm(response, tool_call_id, model_id)

        result = response.content
        return str(result) if result else content
