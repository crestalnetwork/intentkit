"""Skills for searching the web via different providers."""

import logging
from typing import Annotated, Literal, override

import httpx
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill

logger = logging.getLogger(__name__)

ZAI_API_BASE = "https://api.z.ai/api/coding/paas/v4"


class SearchWebInput(BaseModel):
    """Input schema for web search."""

    query: str = Field(..., description="The search query")
    search_recency_filter: (
        Literal["oneDay", "oneWeek", "oneMonth", "oneYear"] | None
    ) = Field(
        default=None,
        description="Filter results by recency: oneDay, oneWeek, oneMonth, or oneYear. Omit for no time limit.",
    )


class SearchWebZaiSkill(SystemSkill):
    """Skill for searching the web via Z.AI web search API."""

    name: str = "search_web_zai"
    description: str = (
        "Search the web using Z.AI and return relevant results. "
        "Useful when you need to find information on the internet."
    )
    args_schema: ArgsSchema | None = SearchWebInput

    @override
    async def _arun(
        self,
        query: str,
        search_recency_filter: str | None = None,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
    ) -> str:
        """Search the web and return results.

        Args:
            query: The search query.
            search_recency_filter: Optional recency filter.
            tool_call_id: Injected by LangChain runtime.

        Returns:
            Formatted search results.
        """
        try:
            from intentkit.config.config import config

            api_key = config.zai_plan_api_key
            if not api_key:
                raise ToolException(
                    "Z.AI Plan API is not configured. Set ZAI_PLAN_API_KEY."
                )

            results = await self._search(api_key, query, search_recency_filter)
            if not results:
                return "No search results found."

            return self._format_results(results)

        except ToolException:
            raise
        except Exception as e:
            logger.error("search_web_zai failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to search web: {e}") from e

    async def _search(
        self,
        api_key: str,
        query: str,
        search_recency_filter: str | None,
    ) -> list[dict]:
        """Search the web via Z.AI web search API."""
        api_url = f"{ZAI_API_BASE}/web_search"

        body: dict = {
            "search_engine": "search-prime",
            "search_query": query,
            "count": 20,
        }
        if search_recency_filter:
            body["search_recency_filter"] = search_recency_filter

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                api_url,
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        if response.status_code != 200:
            raise ToolException(
                f"Z.AI search API returned status {response.status_code}: {response.text}"
            )

        data = response.json()
        return data.get("search_result", [])

    @staticmethod
    def _format_results(results: list[dict]) -> str:
        """Format search results into readable text."""
        lines = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            content = result.get("content", "")
            link = result.get("link", "")
            publish_date = result.get("publish_date", "")

            entry = f"{i}. **{title}**"
            if content:
                entry += f"\n   {content}"
            if link:
                entry += f"\n   Link: {link}"
            if publish_date:
                entry += f"\n   Published: {publish_date}"
            lines.append(entry)

        return "\n\n".join(lines)
