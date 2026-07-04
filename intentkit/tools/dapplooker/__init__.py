"""DappLooker tools for crypto market data and analytics."""

import logging

from intentkit.config.config import config as system_config
from intentkit.tools.dapplooker.base import DappLookerBaseTool
from intentkit.tools.dapplooker.dapplooker_token_data import DappLookerTokenData

# Cache tools at the system level, because they are stateless
_cache: dict[str, DappLookerBaseTool] = {}

logger = logging.getLogger(__name__)


async def get_tools(tool_names: list[str], **_) -> list[DappLookerBaseTool]:
    """Get the requested DappLooker tools."""
    return [tool for name in tool_names if (tool := get_dapplooker_tool(name))]


def get_dapplooker_tool(tool_name: str) -> DappLookerBaseTool | None:
    """Get a DappLooker tool by name."""
    if tool_name == "dapplooker_token_data":
        if tool_name not in _cache:
            _cache[tool_name] = DappLookerTokenData()
        return _cache[tool_name]
    logger.warning("Unknown DappLooker tool: %s", tool_name)
    return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.dapplooker_api_key)
