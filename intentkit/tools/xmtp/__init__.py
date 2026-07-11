"""XMTP tools."""

from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.xmtp.base import XmtpBaseTool
from intentkit.tools.xmtp.price import XmtpGetSwapPrice
from intentkit.tools.xmtp.swap import XmtpSwap
from intentkit.tools.xmtp.transfer import XmtpTransfer

toolset = ToolsetMeta(
    title="XMTP",
    description="Use this tool only if you want make an XMTP Agent. XMTP protocol tools for creating blockchain transaction requests that can be sent to users for signing",
    tags=["Communication", "Crypto", "DeFi"],
    web3=True,
    icon="/tools/xmtp/xmtp.png",
)


# Cache tools at the module level, because they are stateless
_cache: dict[str, XmtpBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[XmtpBaseTool]] = {
    "xmtp_transfer": XmtpTransfer,
    "xmtp_swap": XmtpSwap,
    "xmtp_get_swap_price": XmtpGetSwapPrice,
}


async def get_tools(tool_names: list[str], **_) -> list[XmtpBaseTool]:
    """Return XMTP tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[XmtpBaseTool] = []
    for name in tool_names:
        tool = get_xmtp_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_xmtp_tool(tool_name: str) -> XmtpBaseTool | None:
    """Get an XMTP tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
