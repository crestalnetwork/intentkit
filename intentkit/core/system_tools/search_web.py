"""Unified web search system tool with multiple backends and quota-aware fallback.

The ``web_search`` tool tries several backends in order so agents on providers
without a native search tool still get reliable web search:

1. A random pick between **Tavily** and **Jina** (only those configured and not
   in a Redis cool-down). On a quota / rate-limit error the backend is put into
   cool-down and the other one is tried.
2. **Gemini** (``gemini-3.6-flash`` with Google Search grounding) as a fallback.
3. **Z.AI** MCP web search as the last resort.

If none of the four backends is configured, a ``ToolException`` is raised.
"""

import logging
import random
from typing import Annotated, override

import httpx
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.mcp.client import McpToolError, call_mcp_tool
from intentkit.clients.mcp.registry import McpServerDef
from intentkit.core.system_tools.base import SystemTool

logger = logging.getLogger(__name__)

_TAVILY_API_URL = "https://api.tavily.com/search"
_JINA_SEARCH_URL = "https://s.jina.ai/"
_GEMINI_SEARCH_MODEL = "gemini-3.6-flash"

# Cool-down window (seconds) applied to a metered backend after it reports a
# quota / rate-limit error, so we stop hammering it. Stored in Redis and shared
# across workers.
_COOLDOWN_TTL = 10 * 60

# HTTP status codes that mean "out of quota / rate limited" for the metered
# backends, as opposed to a transient or configuration error.
_QUOTA_STATUS = frozenset({402, 429, 432, 433})

# MCP server definition for Z.AI web search prime
_ZAI_SEARCH_SERVER = McpServerDef(
    name="zai_web_search_prime",
    display_name="Z.AI Web Search",
    description="Web search via Z.AI MCP",
    url="https://api.z.ai/api/mcp/web_search_prime/mcp",
    transport="streamable_http",
    api_key_config_attr="zai_plan_api_key",
    api_key_header="Authorization",
    api_key_prefix="Bearer",
)


class WebSearchInput(BaseModel):
    """Input schema for web search."""

    query: str = Field(..., description="The search query")
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results to return (1-10).",
    )


class _QuotaError(Exception):
    """Raised internally when a backend is out of quota / rate limited."""


class WebSearchTool(SystemTool):
    """Unified web search tool with quota-aware fallback across backends."""

    name: str = "web_search"
    description: str = (
        "Search the web and return relevant results. "
        "Useful when you need to find current information on the internet."
    )
    args_schema: ArgsSchema | None = WebSearchInput

    @override
    async def _arun(
        self,
        query: str,
        max_results: int = 5,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
    ) -> str:
        """Search the web, falling back across backends as needed."""
        from intentkit.config.config import config

        has_tavily = bool(config.tavily_api_key)
        has_jina = bool(config.jina_api_key)
        has_gemini = bool(config.google_api_key)
        has_zai = bool(config.zai_plan_api_key)

        if not (has_tavily or has_jina or has_gemini or has_zai):
            raise ToolException(
                "No web search backend is configured. Set at least one of "
                "TAVILY_API_KEY, JINA_API_KEY, GOOGLE_API_KEY, or ZAI_PLAN_API_KEY."
            )

        errors: list[str] = []

        # 1. A random pick between Tavily / Jina. Cooldown is checked lazily as
        #    each backend is reached, so a successful first call avoids the
        #    second Redis round-trip.
        candidates: list[str] = []
        if has_tavily:
            candidates.append("tavily")
        if has_jina:
            candidates.append("jina")
        random.shuffle(candidates)

        for backend in candidates:
            if await self._in_cooldown(backend):
                continue
            try:
                if backend == "tavily":
                    return await self._search_tavily(
                        config.tavily_api_key, query, max_results
                    )
                return await self._search_jina(config.jina_api_key, query, max_results)
            except _QuotaError as e:
                await self._set_cooldown(backend)
                errors.append(f"{backend} out of quota ({e})")
            except ToolException as e:
                errors.append(f"{backend} failed ({e})")

        # 2. Gemini (Google) fallback.
        if has_gemini:
            try:
                return await self._search_gemini(query, max_results, tool_call_id)
            except Exception as e:
                errors.append(f"gemini failed ({e})")

        # 3. Z.AI as the last resort.
        if has_zai:
            try:
                return await self._search_zai(config.zai_plan_api_key, query)
            except Exception as e:
                errors.append(f"zai failed ({e})")

        raise ToolException(
            "All web search backends are unavailable: " + "; ".join(errors)
        )

    # ── Quota cool-down (Redis) ────────────────────────────────────────────

    @staticmethod
    def _cooldown_key(backend: str) -> str:
        return f"intentkit:web_search:cooldown:{backend}"

    async def _in_cooldown(self, backend: str) -> bool:
        """Return True if the backend is cooling down. Fails open on Redis errors."""
        try:
            from intentkit.config.redis import get_redis

            redis = get_redis()
            return bool(await redis.exists(self._cooldown_key(backend)))
        except Exception:
            return False

    async def _set_cooldown(self, backend: str) -> None:
        """Mark a backend as cooling down. Best-effort; ignores Redis errors."""
        try:
            from intentkit.config.redis import get_redis

            redis = get_redis()
            await redis.set(self._cooldown_key(backend), 1, ex=_COOLDOWN_TTL)
            logger.warning(
                "web_search: %s hit quota, cooling down for %ss", backend, _COOLDOWN_TTL
            )
        except Exception as e:
            logger.warning("web_search: failed to set cooldown for %s: %s", backend, e)

    # ── Backends ───────────────────────────────────────────────────────────

    async def _search_tavily(
        self, api_key: str | None, query: str, max_results: int
    ) -> str:
        """Search via Tavily."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                },
            )

        if response.status_code in _QUOTA_STATUS:
            raise _QuotaError(f"status {response.status_code}")
        if response.status_code != 200:
            raise ToolException(f"Tavily error {response.status_code}: {response.text}")

        results = response.json().get("results", [])
        return self._format_results(
            query,
            [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("content"),
                }
                for r in results
            ],
        )

    async def _search_jina(
        self, api_key: str | None, query: str, max_results: int
    ) -> str:
        """Search via Jina (s.jina.ai)."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                _JINA_SEARCH_URL,
                params={"q": query},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    # Return result metadata only, not full page content.
                    "X-Respond-With": "no-content",
                },
            )

        if response.status_code in _QUOTA_STATUS:
            raise _QuotaError(f"status {response.status_code}")
        if response.status_code != 200:
            raise ToolException(f"Jina error {response.status_code}: {response.text}")

        items = response.json().get("data", [])[:max_results]
        return self._format_results(
            query,
            [
                {
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "snippet": it.get("description") or it.get("content"),
                }
                for it in items
            ],
        )

    async def _search_gemini(
        self, query: str, max_results: int, tool_call_id: str | None
    ) -> str:
        """Search via gemini-3.6-flash with Google Search grounding."""
        from intentkit.models.llm import create_llm_model

        # Collecting and formatting search results needs little reasoning;
        # the catalog default (high) would burn thinking tokens per search.
        llm_model = await create_llm_model(_GEMINI_SEARCH_MODEL, reasoning_effort="low")
        llm = await llm_model.create_instance()
        grounded = llm.bind_tools([{"google_search": {}}])

        response = await grounded.ainvoke(
            [
                {
                    "role": "user",
                    "content": (
                        f"Search the web for: {query}\n\n"
                        f"Return up to {max_results} relevant results. Format each "
                        "result on its own lines exactly as:\n"
                        "<number>. <title>\n<one-sentence summary>\nSource: <url>"
                    ),
                }
            ]
        )

        await self._bill_internal_llm(response, tool_call_id, _GEMINI_SEARCH_MODEL)

        result = response.content
        if not result:
            raise ToolException("Gemini search returned no content")
        return result if isinstance(result, str) else str(result)

    async def _search_zai(self, api_key: str | None, query: str) -> str:
        """Search via Z.AI MCP web search prime."""
        try:
            return await call_mcp_tool(
                _ZAI_SEARCH_SERVER, api_key, "web_search_prime", {"search_query": query}
            )
        except McpToolError as e:
            raise ToolException(str(e)) from e

    # ── Helpers ────────────────────────────────────────────────────────────

    def _format_results(self, query: str, items: list[dict]) -> str:
        """Format backend results into a uniform numbered list."""
        items = [it for it in items if it.get("url")]
        if not items:
            return f"No results found for query: '{query}'"

        formatted = f"Web search results for: '{query}'\n\n"
        for i, item in enumerate(items, 1):
            formatted += f"{i}. {item.get('title') or 'No title'}\n"
            snippet = (item.get("snippet") or "").strip()
            if snippet:
                formatted += f"{snippet[:500]}\n"
            formatted += f"Source: {item['url']}\n\n"
        return formatted.strip()
