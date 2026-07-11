"""Elfa tools."""

import logging
from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.elfa.base import ElfaBaseTool
from intentkit.tools.elfa.mention import (
    ElfaGetTopMentions,
    ElfaSearchMentions,
)
from intentkit.tools.elfa.stats import ElfaGetSmartStats
from intentkit.tools.elfa.tokens import ElfaGetTrendingTokens
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Elfa",
    description="Integration with Elfa AI API providing data analysis and processing capabilities with secure authentication for advanced data operations",
    tags=["AI", "Analytics"],
    web3=True,
    icon="/tools/elfa/elfa.jpg",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, ElfaBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_CLASSES: dict[str, Callable[[], ElfaBaseTool]] = {
    "elfa_get_top_mentions": ElfaGetTopMentions,
    "elfa_search_mentions": ElfaSearchMentions,
    "elfa_get_trending_tokens": ElfaGetTrendingTokens,
    "elfa_get_smart_stats": ElfaGetSmartStats,
}


async def get_tools(tool_names: list[str], **_) -> list[ElfaBaseTool]:
    """Get the requested Elfa tools."""
    return [tool for name in tool_names if (tool := get_elfa_tool(name))]


def get_elfa_tool(tool_name: str) -> ElfaBaseTool | None:
    """Get an Elfa tool by name."""
    if tool_name not in _cache:
        tool_class = _TOOL_CLASSES.get(tool_name)
        if tool_class is None:
            logger.warning("Unknown Elfa tool: %s", tool_name)
            return None
        _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.elfa_api_key)
