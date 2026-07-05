"""Helpers for inspecting which tools are usable in the current deployment.

A toolset exposes a module-level ``available()`` callable that checks
its system config (API keys, env vars, etc.). Individual tools inside a
category may also override ``available()`` on the tool class for
finer-grained gating (e.g. a per-tool API key). These helpers wrap both
layers so the catalog rendering in ``intentkit/core/agent/tool_registry.py``
can drop everything that wouldn't actually run; per-tool checks resolve
through the class registry, so they work uniformly in every category.
"""

from __future__ import annotations

import logging
from types import ModuleType

logger = logging.getLogger(__name__)


def is_toolset_available(module: ModuleType) -> bool:
    """Whether the category module reports itself available.

    Missing ``available()`` defaults to True; a raising ``available()``
    defaults to False so a misconfigured tool never blocks the listing.
    """
    available_fn = getattr(module, "available", None)
    if available_fn is None:
        return True
    try:
        return bool(available_fn())
    except Exception as exc:
        logger.debug(
            "available() raised for category module %r: %s", module.__name__, exc
        )
        return False


def is_individual_tool_available(category: str, tool_name: str) -> bool:
    """Whether a specific tool within a category reports itself available.

    Resolves the tool through the class registry's singleton (every getter
    the toolsets used to expose was an identical cache lookup, so one
    resolution path serves all categories). Defaults to True when the tool
    is unknown so a listing never breaks on a missing class (e.g. MCP
    catalogs have no backing classes).
    """
    from intentkit.tools.base import get_tool_instance

    tool = get_tool_instance(tool_name)
    if tool is None:
        return True
    try:
        return bool(tool.available())
    except Exception as exc:
        logger.debug(
            "available() raised for tool '%s/%s': %s", category, tool_name, exc
        )
        return False
