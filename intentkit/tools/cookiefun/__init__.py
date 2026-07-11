from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.cookiefun.base import CookieFunBaseTool, logger
from intentkit.tools.cookiefun.get_account_details import GetAccountDetails
from intentkit.tools.cookiefun.get_account_feed import GetAccountFeed
from intentkit.tools.cookiefun.get_account_smart_followers import (
    GetAccountSmartFollowers,
)
from intentkit.tools.cookiefun.get_sectors import GetSectors
from intentkit.tools.cookiefun.search_accounts import SearchAccounts
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="CookieFun Tools",
    description="Access Twitter/X analytics and insights using CookieFun API. Get data about accounts, tweets, followers, and trends across different industry sectors.",
    tags=["Analytics", "Social"],
    web3=True,
    icon="/tools/cookiefun/cookiefun.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, CookieFunBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], CookieFunBaseTool]] = {
    "cookiefun_get_sectors": GetSectors,
    "cookiefun_get_account_details": GetAccountDetails,
    "cookiefun_get_account_smart_followers": GetAccountSmartFollowers,
    "cookiefun_search_accounts": SearchAccounts,
    "cookiefun_get_account_feed": GetAccountFeed,
}


async def get_tools(tool_names: list[str], **_) -> list[CookieFunBaseTool]:
    """Get the requested CookieFun tools."""
    tools = [tool for name in tool_names if (tool := get_cookiefun_tool(name))]
    logger.info("Returning %d CookieFun tools", len(tools))
    return tools


def get_cookiefun_tool(tool_name: str) -> CookieFunBaseTool | None:
    """Get a CookieFun tool by name."""
    if tool_name not in _cache:
        tool_class = _TOOL_CLASSES.get(tool_name)
        if tool_class is None:
            logger.warning("Unknown CookieFun tool: %s", tool_name)
            return None
        _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cookiefun_api_key)
