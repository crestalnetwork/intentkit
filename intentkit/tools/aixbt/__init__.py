"""AIXBT API tools."""

from typing import Any

from intentkit.config.config import config as system_config
from intentkit.tools.aixbt.base import AIXBTBaseTool
from intentkit.tools.aixbt.projects import AIXBTProjects

# Cache tools at the system level, because they are stateless
_cache: dict[str, AIXBTBaseTool] = {}


async def get_tools(tool_names: list[str], **_: Any) -> list[AIXBTBaseTool]:
    """Return AIXBT tool instances for the requested names."""
    result: list[AIXBTBaseTool] = []
    for name in tool_names:
        tool = get_aixbt_tool(name)
        if tool:
            result.append(tool)
    return result


def get_aixbt_tool(name: str) -> AIXBTBaseTool | None:
    """Get an AIXBT API tool by name."""
    if name == "aixbt_projects":
        if name not in _cache:
            _cache[name] = AIXBTProjects()
        return _cache[name]
    return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.aixbt_api_key)
