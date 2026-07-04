"""Tool registry utilities.

Loads tool schemas from ``intentkit.tools.<category>/schema.json`` and uses them
to validate/sanitize an agent's ``tools`` config and to render a human/LLM
readable catalog of the tools available in this deployment.

These helpers are deployment-aware: categories whose system config (API keys,
etc.) is not present are filtered out via ``intentkit.tools.availability`` so the
LLM never advertises a tool that could never run.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import jsonref

from intentkit.tools.availability import (
    import_toolset,
    is_individual_tool_available,
    is_toolset_available,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def _load_tool_schema(schema_path: Path) -> dict[str, object]:
    base_uri = f"file://{schema_path}"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        embedded_schema: dict[str, object] = cast(
            dict[str, object],
            jsonref.load(
                schema_file, base_uri=base_uri, proxies=False, lazy_load=False
            ),
        )

    schema_copy = dict(embedded_schema)
    _ = schema_copy.setdefault(
        "title", schema_path.parent.name.replace("_", " ").title()
    )
    return schema_copy


def _get_tools_map(tool_schema: dict[str, object]) -> dict[str, Any] | None:
    """Extract the ``tools`` catalog map from a toolset schema, or None."""
    tools = tool_schema.get("tools", {})
    return cast(dict[str, Any], tools) if isinstance(tools, dict) else None


def _iter_tool_schemas(
    *, require_available: bool = False
) -> Iterator[tuple[str, ModuleType | None, dict[str, object]]]:
    """Yield ``(category, module, schema)`` for each loadable tool schema.

    Walks ``intentkit/tools/*/schema.json`` in sorted category order, loading
    each schema and skipping (with a warning) any that fail to parse. When
    ``require_available`` is True the toolset module is imported and categories
    whose ``available()`` reports False are skipped; ``module`` is then the
    imported toolset, and None otherwise.

    Raises ``AttributeError``/``ModuleNotFoundError``/``ImportError`` if the
    ``intentkit.tools`` package itself cannot be located — callers decide how to
    surface that.
    """
    traversable = resources.files("intentkit.tools")
    with resources.as_file(traversable) as tools_root:
        for entry in sorted(tools_root.iterdir(), key=lambda p: p.name):
            if not entry.is_dir():
                continue

            schema_path = entry / "schema.json"
            if not schema_path.is_file():
                continue

            category = entry.name

            module: ModuleType | None = None
            if require_available:
                module = import_toolset(category)
                if module is None or not is_toolset_available(module):
                    logger.info("Skipped toolset '%s': not available", category)
                    continue

            try:
                tool_schema = _load_tool_schema(schema_path)
            except (
                OSError,
                ValueError,
                json.JSONDecodeError,
                jsonref.JsonRefError,
            ) as exc:
                logger.warning("Failed to load schema for tool '%s': %s", category, exc)
                continue

            yield category, module, tool_schema


@lru_cache(maxsize=1)
def get_valid_tools_registry() -> dict[str, dict[str, str]]:
    """Load all tool schemas and return a registry of valid tools.

    Returns a nested dict mapping category name to a dict of tool names
    and their descriptions: ``{category: {tool_name: description}}``.

    Broken or unreadable schemas are silently skipped. The result is cached for
    the process lifetime: tool schemas ship with the code and never change at
    runtime, so this is recomputed only after a restart. Callers must treat the
    returned dict as read-only.
    """
    registry: dict[str, dict[str, str]] = {}
    try:
        for category, _module, tool_schema in _iter_tool_schemas():
            tools_map = _get_tools_map(tool_schema)
            if not tools_map:
                continue

            tools: dict[str, str] = {}
            for tool_name, tool_def in tools_map.items():
                if isinstance(tool_def, dict):
                    description = tool_def.get("description", "")
                    if isinstance(description, str):
                        tools[tool_name] = description

            if tools:
                registry[category] = tools

    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit tools package not found when building tools registry")

    return registry


def get_tool_category_index() -> dict[str, str]:
    """Map every known tool name to its category.

    Derived from the cached registry on every call (cheap dict build), so it
    can never go stale relative to ``get_valid_tools_registry``.
    """
    index: dict[str, str] = {}
    for category, tools in get_valid_tools_registry().items():
        for tool_name in tools:
            existing = index.get(tool_name)
            if existing is not None:
                logger.warning(
                    "Tool name '%s' defined by both '%s' and '%s'; using '%s'",
                    tool_name,
                    existing,
                    category,
                    category,
                )
            index[tool_name] = category
    return index


def group_tool_names_by_category(tool_names: list[str]) -> dict[str, list[str]]:
    """Group requested tool names by their toolset category.

    Unknown names are skipped with a warning: stale entries (e.g. a tool
    removed from the codebase) must never break agent startup.
    """
    index = get_tool_category_index()
    grouped: dict[str, list[str]] = {}
    for name in tool_names:
        category = index.get(name)
        if category is None:
            logger.warning("Skipping unknown tool '%s' in agent config", name)
            continue
        grouped.setdefault(category, []).append(name)
    return grouped


def validate_tools(tools: Any) -> None:
    """Validate a tools name list. Raises IntentKitAPIError(400) on invalid entries."""
    if not tools:
        return

    if not isinstance(tools, list):
        raise IntentKitAPIError(
            400,
            "InvalidToolFormat",
            f"'tools' must be a list of tool names, got {type(tools).__name__}",
        )

    index = get_tool_category_index()
    for name in tools:
        if not isinstance(name, str):
            raise IntentKitAPIError(
                400,
                "InvalidToolFormat",
                f"Tool names must be strings, got {type(name).__name__}",
            )
        if name not in index:
            raise IntentKitAPIError(
                400,
                "InvalidToolName",
                f"Unknown tool '{name}'. Use the tool catalog to list valid names.",
            )


def sanitize_tools(tools: list[str] | None) -> list[str] | None:
    """Drop unknown/duplicate tool names. Returns the cleaned list or None if empty."""
    if not tools:
        return None

    index = get_tool_category_index()
    seen: set[str] = set()
    cleaned: list[str] = []
    for name in tools:
        if not isinstance(name, str) or name in seen or name not in index:
            continue
        seen.add(name)
        cleaned.append(name)

    return cleaned if cleaned else None


def get_tools_hierarchical_text() -> str:
    """Extract tools organized by category and return as hierarchical text."""
    # Group tools by category (x-tags)
    categories: dict[str, list[Any]] = {}
    try:
        for category, module, tool_schema in _iter_tool_schemas(require_available=True):
            if module is None:
                # require_available=True guarantees a module; this also narrows
                # the type for is_individual_tool_available below.
                continue

            tool_title = tool_schema.get("title", category.replace("_", " ").title())
            tool_description = tool_schema.get(
                "description", "No description available"
            )
            tool_tags = cast(list[str], tool_schema.get("x-tags", ["Other"]))

            # Use the first tag as the primary group
            primary_category = tool_tags[0] if tool_tags else "Other"

            individual_tools: list[dict[str, str]] = []
            tools_map = _get_tools_map(tool_schema)
            if tools_map:
                for ind_name, ind_def in tools_map.items():
                    if not is_individual_tool_available(module, category, ind_name):
                        continue
                    ind_desc = (
                        ind_def.get("description", "No description available")
                        if isinstance(ind_def, dict)
                        else "No description available"
                    )
                    individual_tools.append({"name": ind_name, "description": ind_desc})

            # Drop the category entirely if every tool was filtered;
            # surfacing an empty group would just be noise to the LLM.
            if tools_map and not individual_tools:
                continue

            if primary_category not in categories:
                categories[primary_category] = []

            categories[primary_category].append(
                {
                    "name": category,
                    "title": tool_title,
                    "description": tool_description,
                    "individual_tools": individual_tools,
                }
            )
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit tools package not found when building tools text")
        return "No tools available"

    # Build hierarchical text
    text_lines = []
    text_lines.append("Available Tools by Category:")
    text_lines.append("")

    # Sort categories alphabetically
    for category in sorted(categories.keys()):
        text_lines.append(f"#### {category}")
        text_lines.append("")

        # Sort tools within category alphabetically by name
        for tool in sorted(categories[category], key=lambda x: x["name"]):
            text_lines.append(
                f"- **{tool['name']}** ({tool['title']}): {tool['description']}"
            )
            # Add individual tools indented under the category tool
            for ind_tool in sorted(
                tool.get("individual_tools", []), key=lambda x: x["name"]
            ):
                text_lines.append(
                    f"  - `{ind_tool['name']}`: {ind_tool['description']}"
                )

        text_lines.append("")

    return "\n".join(text_lines)
