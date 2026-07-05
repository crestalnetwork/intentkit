"""Tool registry utilities.

Builds the tool catalog from code: each toolset package declares a
module-level ``toolset`` (:class:`ToolsetMeta`) and its tools are the
``IntentKitTool`` subclasses defined in the package (MCP-backed categories
declare a fixed ``tools`` override instead, since their real tools are
discovered live from the remote server). The catalog drives validation and
sanitization of an agent's ``tools`` config, the picker payload served to
frontends, and a human/LLM readable listing.

These helpers are deployment-aware where it matters: catalog renderings for
users/LLMs filter out categories whose system config (API keys, etc.) is not
present via ``intentkit.tools.availability``, while validation accepts every
tool that exists in the codebase.

Everything here is cached for the process lifetime: the catalog ships with
the code and availability depends only on process-static system config.
Callers must treat all returned structures as read-only. The first build
imports every toolset module (seconds) — call :func:`warm_tool_registry`
from app startup so no request or message pays that wall.
"""

from __future__ import annotations

import importlib
import logging
from functools import lru_cache
from types import ModuleType
from typing import Any, NamedTuple

import intentkit.tools as tools_pkg
from intentkit.tools.availability import (
    is_individual_tool_available,
    is_toolset_available,
)
from intentkit.tools.base import (
    build_tool_prices,
    collect_tool_classes,
    tool_field_default,
)
from intentkit.tools.meta import ToolMeta, ToolsetMeta
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


class _CategoryEntry(NamedTuple):
    meta: ToolsetMeta
    module: ModuleType
    tools: dict[str, ToolMeta]


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, _CategoryEntry]:
    """Import every toolset package and derive the full catalog from code."""
    tool_classes = collect_tool_classes()

    metas: dict[str, tuple[ToolsetMeta, ModuleType]] = {}
    for module_name in tools_pkg.__all__:
        try:
            module = importlib.import_module(f"intentkit.tools.{module_name}")
        except Exception:  # already logged by collect_tool_classes' import walk
            continue
        meta = getattr(module, "toolset", None)
        if isinstance(meta, ToolsetMeta):
            metas[module_name] = (meta, module)

    tools_by_category: dict[str, dict[str, ToolMeta]] = {cat: {} for cat in metas}
    name_owner: dict[str, str] = {}
    for cls in tool_classes:
        name = tool_field_default(cls, "name")
        if not isinstance(name, str) or not name:
            continue  # abstract/base classes have no concrete name
        category = tool_field_default(cls, "category")
        if category not in tools_by_category:
            continue  # not part of a declared toolset (e.g. test doubles)
        owner = name_owner.get(name)
        if owner is not None:
            # Same category: two classes claim one tool name (one is lost).
            # Different categories: the name is ambiguous across toolsets.
            logger.warning(
                "Tool name '%s' defined by both '%s' and '%s'; using '%s'",
                name,
                owner,
                category,
                category,
            )
        name_owner[name] = category
        title = tool_field_default(cls, "title")
        description = tool_field_default(cls, "description")
        tools_by_category[category][name] = ToolMeta(
            title=title if isinstance(title, str) and title else name,
            description=description if isinstance(description, str) else "",
            team_only=bool(tool_field_default(cls, "team_only")),
        )

    catalog: dict[str, _CategoryEntry] = {}
    for category in sorted(metas):
        meta, module = metas[category]
        if meta.tools is not None:
            if tools_by_category[category]:
                logger.warning(
                    "Toolset '%s' declares an explicit tools override; ignoring "
                    "%d tool class(es) found in the package",
                    category,
                    len(tools_by_category[category]),
                )
            tools = dict(meta.tools)
        else:
            tools = dict(sorted(tools_by_category[category].items()))
        if not tools:
            logger.warning("Toolset '%s' declares no tools; skipping", category)
            continue
        catalog[category] = _CategoryEntry(meta=meta, module=module, tools=tools)

    return catalog


def _category_payload(meta: ToolsetMeta, tools: dict[str, ToolMeta]) -> dict[str, Any]:
    """Render one category in the wire shape frontends consume (x-catalog)."""
    payload: dict[str, Any] = {
        "title": meta.title,
        "description": meta.description,
        "x-tags": list(meta.tags),
    }
    if meta.icon:
        payload["x-icon"] = meta.icon
    if meta.web3:
        payload["x-web3"] = True
    payload["tools"] = {
        name: {"title": tool.title, "description": tool.description}
        for name, tool in tools.items()
    }
    return payload


@lru_cache(maxsize=2)
def get_tool_catalog(*, available_only: bool = False) -> dict[str, dict[str, Any]]:
    """The full toolset catalog in the wire shape served to frontends.

    With ``available_only`` the result is filtered to categories (and
    individual tools) usable in the current deployment; otherwise every tool
    in the codebase is included.
    """
    result: dict[str, dict[str, Any]] = {}
    for category, entry in _load_catalog().items():
        tools = entry.tools
        if available_only:
            if not is_toolset_available(entry.module):
                logger.info("Skipped toolset '%s': not available", category)
                continue
            tools = {
                name: tool
                for name, tool in tools.items()
                if is_individual_tool_available(entry.module, category, name)
            }
            if not tools:
                continue
        result[category] = _category_payload(entry.meta, tools)
    return result


@lru_cache(maxsize=1)
def get_web3_categories() -> frozenset[str]:
    """Categories whose tools operate on team wallets (``web3`` in their meta).

    These are only selectable for agents whose team owns at least one
    wallet, and their tools take a ``wallet_address`` chosen by the agent.
    """
    return frozenset(
        category for category, entry in _load_catalog().items() if entry.meta.web3
    )


@lru_cache(maxsize=1)
def get_team_only_tool_names() -> frozenset[str]:
    """Tool names hidden from guests of a published agent (``team_only``)."""
    return frozenset(
        name
        for entry in _load_catalog().values()
        for name, tool in entry.tools.items()
        if tool.team_only
    )


def filter_web3_tool_names(tool_names: list[str]) -> list[str]:
    """The subset of the given tool names that belong to web3 categories."""
    web3 = get_web3_categories()
    index = get_tool_category_index()
    return [name for name in tool_names if index.get(name) in web3]


@lru_cache(maxsize=1)
def get_tool_category_index() -> dict[str, str]:
    """Map every known tool name to its category (name collisions warned at load)."""
    return {
        tool_name: category
        for category, entry in _load_catalog().items()
        for tool_name in entry.tools
    }


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
    catalog = get_tool_catalog(available_only=True)

    # Group toolsets by their primary tag
    groups: dict[str, list[dict[str, Any]]] = {}
    for category, payload in catalog.items():
        tags = payload.get("x-tags") or ["Other"]
        groups.setdefault(tags[0], []).append(
            {
                "name": category,
                "title": payload["title"],
                "description": payload["description"],
                "individual_tools": [
                    {"name": name, "description": info["description"]}
                    for name, info in payload["tools"].items()
                ],
            }
        )

    if not groups:
        return "No tools available"

    text_lines = ["Available Tools by Category:", ""]
    for group in sorted(groups.keys()):
        text_lines.append(f"#### {group}")
        text_lines.append("")
        for toolset in sorted(groups[group], key=lambda x: x["name"]):
            text_lines.append(
                f"- **{toolset['name']}** ({toolset['title']}): {toolset['description']}"
            )
            for tool in sorted(toolset["individual_tools"], key=lambda x: x["name"]):
                text_lines.append(f"  - `{tool['name']}`: {tool['description']}")
        text_lines.append("")

    return "\n".join(text_lines)


def warm_tool_registry() -> None:
    """Pay the one-time toolset import/scan cost up front.

    Call from app startup (off the event loop, e.g. ``asyncio.to_thread``) so
    no request or chat message stalls on the first catalog build.
    """
    _ = get_tool_catalog(available_only=True)
    build_tool_prices()
