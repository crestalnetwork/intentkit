"""Helpers for inspecting which tools are usable in the current deployment.

A toolset exposes a module-level ``available()`` callable that checks
its system config (API keys, env vars, etc.). Individual tools inside a
category may also expose ``available()`` on the instance for finer-grained
gating (e.g. wallet/scope checks). These helpers wrap both layers so callers
that build user-facing tool listings (``app/common/schema.py``,
``intentkit/core/agent/tool_registry.py``) can drop everything that wouldn't
actually run.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any, Callable

logger = logging.getLogger(__name__)


def import_toolset(category: str) -> ModuleType | None:
    """Import a toolset module, returning None on failure."""
    try:
        return importlib.import_module(f"intentkit.tools.{category}")
    except Exception as exc:
        logger.warning("Could not import toolset '%s': %s", category, exc)
        return None


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


def find_tool_getter(module: ModuleType, category: str) -> Callable[..., Any] | None:
    """Locate the ``get_<name>_tool`` accessor for a category module.

    Convention is ``get_{category}_tool``; falls back to any ``get_*_tool``
    attribute (e.g. ``moralis`` exposes ``get_wallet_tool``).
    """
    getter = getattr(module, f"get_{category}_tool", None)
    if getter is not None:
        return getter
    for attr_name in dir(module):
        if attr_name.startswith("get_") and attr_name.endswith("_tool"):
            return getattr(module, attr_name)
    return None


def is_individual_tool_available(
    module: ModuleType, category: str, tool_name: str
) -> bool:
    """Whether a specific tool within a category reports itself available.

    Defaults to True when the module has no getter, the getter raises, the
    tool instance is None, or the tool exposes no ``available()``.
    """
    getter = find_tool_getter(module, category)
    if getter is None:
        return True
    try:
        tool = getter(tool_name)
    except Exception as exc:
        logger.debug("Tool getter raised for '%s/%s': %s", category, tool_name, exc)
        return True
    if tool is None:
        return True
    available_fn = getattr(tool, "available", None)
    if available_fn is None:
        return True
    try:
        return bool(available_fn())
    except Exception as exc:
        logger.debug(
            "available() raised for tool '%s/%s': %s", category, tool_name, exc
        )
        return False


def filter_unavailable_tools(
    module: ModuleType, category: str, tools_map: dict[str, Any]
) -> dict[str, Any]:
    """Drop unavailable individual tools from a schema ``tools`` catalog map.

    Returns a new dict; the input is not mutated.
    """
    filtered: dict[str, Any] = {}
    for tool_name, tool_schema in tools_map.items():
        if not is_individual_tool_available(module, category, tool_name):
            logger.info("Filtered out tool '%s/%s': not available", category, tool_name)
            continue
        filtered[tool_name] = tool_schema
    return filtered
