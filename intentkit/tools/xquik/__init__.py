"""Xquik tools for public X research."""

import logging
from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.xquik.base import XquikBaseTool
from intentkit.tools.xquik.search_tweets import XquikSearchTweets

toolset = ToolsetMeta(
    title="Xquik",
    description=(
        "Search public X posts through Xquik. Xquik is an independent third-party "
        'service. Not affiliated with X Corp. "Twitter" and "X" are trademarks '
        "of X Corp."
    ),
    tags=["Search", "Social"],
    icon="/tools/xquik/xquik.svg",
)

logger = logging.getLogger(__name__)

_cache: dict[str, XquikBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], XquikBaseTool]] = {
    "xquik_search_tweets": XquikSearchTweets,
}


async def get_tools(tool_names: list[str], **_) -> list[XquikBaseTool]:
    """Return requested Xquik tools and skip unknown names."""
    return [tool for name in tool_names if (tool := get_xquik_tool(name))]


def get_xquik_tool(tool_name: str) -> XquikBaseTool | None:
    """Get a cached Xquik tool by name."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_CLASSES.get(tool_name)
    if tool_class is None:
        logger.warning("Unknown Xquik tool: %s", tool_name)
        return None

    _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check whether the hosted Xquik credential is configured."""
    return bool(system_config.xquik_api_key)
