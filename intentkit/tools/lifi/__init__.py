from collections.abc import Callable

from intentkit.tools.lifi.base import LiFiBaseTool
from intentkit.tools.lifi.token_execute import TokenExecute
from intentkit.tools.lifi.token_quote import TokenQuote
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="LiFi Token Transfer",
    description="Cross-chain token transfer and swap capabilities using the LiFi protocol",
    tags=["DeFi"],
    wallet=True,
    icon="/tools/lifi/lifi.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, LiFiBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], LiFiBaseTool]] = {
    "lifi_token_quote": TokenQuote,
    "lifi_token_execute": TokenExecute,
}


async def get_tools(tool_names: list[str], **_) -> list[LiFiBaseTool]:
    """Get the requested LiFi tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_lifi_tool(name))]


def get_lifi_tool(tool_name: str) -> LiFiBaseTool | None:
    """Get a LiFi tool by name, using the instance cache and built-in defaults."""
    if tool_name in _cache:
        return _cache[tool_name]
    cls = _TOOL_CLASSES.get(tool_name)
    if cls is None:
        return None
    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
