"""Chainlist tools for blockchain RPC endpoint lookup."""

from typing import Any

from intentkit.tools.chainlist.base import ChainlistBaseTool
from intentkit.tools.chainlist.chain_lookup import ChainLookup

# Cache tools at the system level, because they are stateless
_cache: dict[str, ChainlistBaseTool] = {}


async def get_tools(tool_names: list[str], **_: Any) -> list[ChainlistBaseTool]:
    """Return chainlist tool instances for the requested names."""
    result: list[ChainlistBaseTool] = []
    for name in tool_names:
        tool = get_chainlist_tool(name)
        if tool:
            result.append(tool)
    return result


def get_chainlist_tool(name: str) -> ChainlistBaseTool | None:
    """Get a chainlist tool by name."""
    if name == "chain_lookup":
        if name not in _cache:
            _cache[name] = ChainLookup()
        return _cache[name]
    return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
