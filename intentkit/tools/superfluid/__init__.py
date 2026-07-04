"""Superfluid streaming payment tools."""

from intentkit.tools.superfluid.base import SuperfluidBaseTool
from intentkit.tools.superfluid.create_flow import SuperfluidCreateFlow
from intentkit.tools.superfluid.delete_flow import SuperfluidDeleteFlow
from intentkit.tools.superfluid.update_flow import SuperfluidUpdateFlow

# Cache for tool instances
_cache: dict[str, SuperfluidBaseTool] = {
    "superfluid_create_flow": SuperfluidCreateFlow(),
    "superfluid_update_flow": SuperfluidUpdateFlow(),
    "superfluid_delete_flow": SuperfluidDeleteFlow(),
}


async def get_tools(tool_names: list[str], **_) -> list[SuperfluidBaseTool]:
    """Return Superfluid tool instances for the requested names.

    Unknown names are skipped silently.
    """
    return [_cache[name] for name in tool_names if name in _cache]


def get_superfluid_tool(tool_name: str) -> SuperfluidBaseTool | None:
    """Get a Superfluid tool by name."""
    return _cache.get(tool_name)


def available() -> bool:
    """Check if this toolset is available based on system config.

    Superfluid tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
