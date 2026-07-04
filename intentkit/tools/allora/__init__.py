"""Allora tool module."""

from typing import Any

from intentkit.config.config import config as system_config
from intentkit.tools.allora.base import AlloraBaseTool
from intentkit.tools.allora.price import AlloraGetPrice

# Cache tools at the system level, because they are stateless
_cache: dict[str, AlloraBaseTool] = {}


async def get_tools(tool_names: list[str], **_: Any) -> list[AlloraBaseTool]:
    """Return Allora tool instances for the requested names."""
    result: list[AlloraBaseTool] = []
    for name in tool_names:
        tool = get_allora_tool(name)
        if tool:
            result.append(tool)
    return result


def get_allora_tool(name: str) -> AlloraBaseTool | None:
    """Get an Allora tool by name."""
    if name == "allora_get_price_prediction":
        if name not in _cache:
            _cache[name] = AlloraGetPrice()
        return _cache[name]
    return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.allora_api_key)
