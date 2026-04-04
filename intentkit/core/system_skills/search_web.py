"""Skills for searching the web via different providers."""

import logging
from typing import Annotated, Literal, override

from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.mcp.client import McpToolError, call_mcp_tool
from intentkit.clients.mcp.registry import McpServerDef
from intentkit.core.system_skills.base import SystemSkill

logger = logging.getLogger(__name__)

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
    """Skill for searching the web via Z.AI MCP web search prime."""

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
        """Search the web via Z.AI MCP and return results."""
        try:
            from intentkit.config.config import config

            api_key = config.zai_plan_api_key
            if not api_key:
                raise ToolException(
                    "Z.AI Plan API is not configured. Set ZAI_PLAN_API_KEY."
                )

            arguments: dict = {"search_query": query}
            if search_recency_filter:
                arguments["search_recency_filter"] = search_recency_filter

            return await call_mcp_tool(
                _ZAI_SEARCH_SERVER, api_key, "web_search_prime", arguments
            )

        except ToolException:
            raise
        except McpToolError as e:
            raise ToolException(str(e)) from e
        except Exception as e:
            logger.error("search_web_zai failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to search web: {e}") from e
