"""Guard against drift between the class-derived tool catalog and each
toolset's runtime.

The catalog (tool_registry._load_catalog) is derived from the IntentKitTool
subclasses found in each toolset package, while the package's ``get_tools``
resolves selected names to runtime tool instances — usually via a hand-written
name → instance map. A tool class that exists but is not wired into that map
means the catalog advertises a tool that can be selected but never actually
loaded (unknown names are silently skipped), so every catalog name must
round-trip through get_tools and come back as an instance whose ``.name``
equals the catalog key.

MCP-backed categories declare a fixed catalog override (one entry keyed by the
server name) and discover their real tools live from the server; for them we
only check that single-entry shape — resolving names would require network
access.
"""

import importlib

import pytest

from intentkit.core.agent.tool_registry import get_tool_catalog


def _catalog_names(category: str) -> list[str]:
    return list(get_tool_catalog()[category]["tools"])


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(get_tool_catalog()))
async def test_catalog_tools_resolve_through_get_tools(name):
    module = importlib.import_module(f"intentkit.tools.{name}")
    catalog_names = _catalog_names(name)
    assert catalog_names, f"{name}: catalog must carry at least one tool"

    if module.toolset.tools is not None:
        # Explicit catalog override (MCP-backed): toggled as a whole, so the
        # catalog must hold exactly one entry keyed by the category/server
        # name; the live tool list is discovered at runtime and cannot be
        # checked statically.
        assert catalog_names == [name], (
            f"{name}: an override catalog must carry the single server-name "
            f"entry {name!r}, got {catalog_names}"
        )
        return

    tools = await module.get_tools(list(catalog_names))
    resolved = sorted(tool.name for tool in tools)
    assert resolved == sorted(catalog_names), (
        f"{name}: catalog diverged from get_tools\n"
        f"  in catalog but not resolved: {sorted(set(catalog_names) - set(resolved))}\n"
        f"  resolved but not in catalog: {sorted(set(resolved) - set(catalog_names))}\n"
        f"Wire the tool class into the module's name map (or remove it)."
    )
