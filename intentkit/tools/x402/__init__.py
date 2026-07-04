"""x402 toolset."""

from intentkit.tools.x402.base import X402BaseTool
from intentkit.tools.x402.check_price import X402CheckPrice
from intentkit.tools.x402.get_orders import X402GetOrders
from intentkit.tools.x402.http_request import X402HttpRequest
from intentkit.tools.x402.pay import X402Pay

# Cache tools at the module level, because they are stateless
_cache: dict[str, X402BaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[X402BaseTool]] = {
    "x402_http_request": X402HttpRequest,
    "x402_check_price": X402CheckPrice,
    "x402_pay": X402Pay,
    "x402_get_orders": X402GetOrders,
}


async def get_tools(tool_names: list[str], **_) -> list[X402BaseTool]:
    """Return x402 tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[X402BaseTool] = []
    for name in tool_names:
        tool = get_x402_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_x402_tool(tool_name: str) -> X402BaseTool | None:
    """Get an x402 tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
