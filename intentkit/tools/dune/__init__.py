"""Dune tools for blockchain analytics via the Dune API."""

import logging
from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.dune.base import DuneBaseTool
from intentkit.tools.dune.execute_query import DuneExecuteQuery
from intentkit.tools.dune.get_query_results import DuneGetQueryResults
from intentkit.tools.dune.run_sql import DuneRunSQL

_cache: dict[str, DuneBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], DuneBaseTool]] = {
    "dune_execute_query": DuneExecuteQuery,
    "dune_get_query_results": DuneGetQueryResults,
    "dune_run_sql": DuneRunSQL,
}


async def get_tools(tool_names: list[str], **_) -> list[DuneBaseTool]:
    """Get the requested Dune tools."""
    return [tool for name in tool_names if (tool := get_dune_tool(name))]


def get_dune_tool(tool_name: str) -> DuneBaseTool | None:
    """Get a Dune tool by name with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    cls = _TOOL_NAME_TO_CLASS.get(tool_name)
    if cls is None:
        logger.warning("Unknown dune tool: %s", tool_name)
        return None

    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.dune_api_key)
