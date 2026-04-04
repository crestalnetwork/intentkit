"""Skills for reading webpage content as markdown via different providers."""

import logging
import re
from typing import Annotated, override

import httpx
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill

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


ZAI_API_BASE = "https://api.z.ai/api/coding/paas/v4"

_MAX_CONTENT_CHARS = 50000


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


class ReadWebpageCloudflareSkill(SystemSkill):
    """Skill for reading webpage content as markdown via Cloudflare.

    Uses Cloudflare Browser Rendering REST API to fetch and convert
    webpages to markdown format, then cleans the content with an LLM.
    """

    name: str = "read_webpage_cloudflare"
    description: str = (
        "Read a webpage using Cloudflare Browser Rendering and return its content as markdown. "
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
                return "The webpage returned no content."

            cleaned = _normalize_whitespace(raw_markdown)

            # Clean content with LLM
            cleaned = await self._clean_with_llm(cleaned, tool_call_id)

            return _truncate(cleaned)

        except ToolException:
            raise
        except Exception as e:
            logger.error("read_webpage failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to read webpage: {e}") from e

    async def _fetch_markdown(self, account_id: str, api_token: str, url: str) -> str:
        """Fetch a URL and convert to markdown via Cloudflare Browser Rendering."""
        api_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/markdown"

        async with httpx.AsyncClient(timeout=60) as client:
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
        llm_model = await create_llm_model(model_id, temperature=0)
        llm = await llm_model.create_instance()

        response = await llm.ainvoke(
            [
                {"role": "system", "content": CLEAN_CONTENT_PROMPT},
                {"role": "user", "content": content},
            ]
        )

        # Bill for the LLM usage
        input_tokens = (
            response.usage_metadata.get("input_tokens", 0)
            if response.usage_metadata
            else 0
        )
        output_tokens = (
            response.usage_metadata.get("output_tokens", 0)
            if response.usage_metadata
            else 0
        )
        cached_input_tokens = (
            response.usage_metadata.get("input_token_details", {}).get("cache_read", 0)
            if response.usage_metadata
            else 0
        )

        try:
            context = self.get_context()
            payer = context.payer
            if payer and tool_call_id:
                from intentkit.core.credit.expense import expense_skill_internal_llm

                await expense_skill_internal_llm(
                    team_id=payer,
                    agent=context.agent,
                    skill_name=self.name,
                    skill_call_id=tool_call_id,
                    start_message_id=context.start_message_id,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                    user_id=context.user_id,
                )
        except Exception as e:
            logger.warning("Failed to bill for LLM cleaning: %s", e)

        result = response.content
        return str(result) if result else content


class ReadWebpageZaiSkill(SystemSkill):
    """Skill for reading webpage content as markdown via Z.AI reader API."""

    name: str = "read_webpage_zai"
    description: str = (
        "Read a webpage using Z.AI reader and return its content as markdown. "
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
            from intentkit.config.config import config

            api_key = config.zai_plan_api_key
            if not api_key:
                raise ToolException(
                    "Z.AI Plan API is not configured. Set ZAI_PLAN_API_KEY."
                )

            raw_markdown = await self._fetch_markdown(api_key, url)
            if not raw_markdown:
                return "The webpage returned no content."

            return _truncate(_normalize_whitespace(raw_markdown))

        except ToolException:
            raise
        except Exception as e:
            logger.error("read_webpage_zai failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to read webpage: {e}") from e

    async def _fetch_markdown(self, api_key: str, url: str) -> str:
        """Fetch a URL and convert to markdown via Z.AI reader API."""
        api_url = f"{ZAI_API_BASE}/reader"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                api_url,
                json={
                    "url": url,
                    "return_format": "markdown",
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )

        if response.status_code != 200:
            raise ToolException(
                f"Z.AI reader API returned status {response.status_code}: {response.text}"
            )

        data = response.json()
        reader_result = data.get("reader_result")
        if not reader_result:
            raise ToolException(f"Z.AI reader API error: {data}")

        return reader_result.get("content", "")
