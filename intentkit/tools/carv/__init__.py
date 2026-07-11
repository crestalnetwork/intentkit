"""CARV API tools."""

import logging
from typing import Any

from intentkit.config.config import config as system_config
from intentkit.tools.carv.base import CarvBaseTool
from intentkit.tools.carv.fetch_news import FetchNewsTool
from intentkit.tools.carv.onchain_query import OnchainQueryTool
from intentkit.tools.carv.token_info_and_price import TokenInfoAndPriceTool
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="CARV",
    description="Configuration for the CARV tool.",
    tags=["Analytics", "Crypto"],
    web3=True,
    icon="/tools/carv/carv.webp",
)


logger = logging.getLogger(__name__)

_cache: dict[str, CarvBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[CarvBaseTool]] = {
    "carv_onchain_query": OnchainQueryTool,
    "carv_token_info_and_price": TokenInfoAndPriceTool,
    "carv_fetch_news": FetchNewsTool,
}


async def get_tools(tool_names: list[str], **_: Any) -> list[CarvBaseTool]:
    """Return CARV tool instances for the requested names."""
    result: list[CarvBaseTool] = []
    for name in tool_names:
        tool = get_carv_tool(name)
        if tool:
            result.append(tool)
    return result


def get_carv_tool(name: str) -> CarvBaseTool | None:
    """Retrieve a cached CARV tool instance by name."""
    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(name)
    if tool_class is None:
        return None

    try:
        # Instantiate the tool and add to cache
        instance = tool_class()  # pyright: ignore[reportCallIssue]
        _cache[name] = instance
        return instance
    except Exception as e:
        logger.error("Failed to instantiate Carv tool '%s': %s", name, e, exc_info=True)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.carv_api_key)
