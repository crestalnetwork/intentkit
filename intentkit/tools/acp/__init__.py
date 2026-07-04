"""ACP (Agentic Commerce Protocol) toolset."""

from typing import Any

from .base import AcpBaseTool
from .cancel_checkout import AcpCancelCheckout
from .complete_checkout import AcpCompleteCheckout
from .create_checkout import AcpCreateCheckout
from .get_checkout import AcpGetCheckout
from .list_products import AcpListProducts

_cache: dict[str, AcpBaseTool] = {}

_TOOL_BUILDERS: dict[str, type[AcpBaseTool]] = {
    "acp_list_products": AcpListProducts,
    "acp_create_checkout": AcpCreateCheckout,
    "acp_get_checkout": AcpGetCheckout,
    "acp_complete_checkout": AcpCompleteCheckout,
    "acp_cancel_checkout": AcpCancelCheckout,
}


async def get_tools(tool_names: list[str], **_: Any) -> list[AcpBaseTool]:
    """Return ACP tool instances for the requested names."""
    result: list[AcpBaseTool] = []
    for name in tool_names:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AcpBaseTool | None:
    builder = _TOOL_BUILDERS.get(name)
    if builder is None:
        return None
    if name not in _cache:
        _cache[name] = builder()
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available."""
    return True
