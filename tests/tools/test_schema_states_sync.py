"""Guard against drift between each toolset's schema.json catalog and its runtime.

The schema.json `tools` map drives the agent tool catalog (tool_registry) and
the config UI, while the module's `get_tools` resolves selected names to
runtime tool instances. A catalog key that get_tools does not accept means a
tool can be selected but never actually loaded (unknown names are silently
skipped), so every catalog key must round-trip through get_tools and come
back as an instance whose `.name` equals the key.

MCP-backed categories discover their tools from the live server at runtime;
their catalog carries a single entry keyed by the server name, which the
wrapper expands to all discovered tools. For them we only check that
single-entry shape — resolving names would require network access.
"""

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest

from intentkit.tools.mcp.wrapper import McpCategoryModule

TOOLS_DIR = Path(__file__).resolve().parents[2] / "intentkit" / "tools"


def _toolset_names():
    return sorted(
        p.name
        for p in TOOLS_DIR.iterdir()
        if p.is_dir() and (p / "schema.json").exists()
    )


def _schema_tool_names(name: str) -> list[str]:
    schema = json.loads((TOOLS_DIR / name / "schema.json").read_text())
    tools = schema.get("tools")
    assert isinstance(tools, dict) and tools, (
        f"{name}/schema.json must carry a non-empty 'tools' catalog map"
    )
    return list(tools)


def _mcp_module(module: ModuleType) -> McpCategoryModule | None:
    """The wrapper instance backing an MCP category module, or None."""
    bound_self = getattr(module.get_tools, "__self__", None)
    return bound_self if isinstance(bound_self, McpCategoryModule) else None


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _toolset_names())
async def test_schema_tools_resolve_through_get_tools(name):
    module = importlib.import_module(f"intentkit.tools.{name}")
    catalog_names = _schema_tool_names(name)

    mcp = _mcp_module(module)
    if mcp is not None:
        # MCP categories are toggled as a whole: the catalog must hold exactly
        # one entry keyed by the server name; the live tool list is discovered
        # at runtime and cannot be checked statically.
        assert catalog_names == [mcp.server_name], (
            f"{name}: MCP catalog must carry the single server-name entry "
            f"{mcp.server_name!r}, got {catalog_names}"
        )
        return

    tools = await module.get_tools(list(catalog_names))
    resolved = sorted(tool.name for tool in tools)
    assert resolved == sorted(catalog_names), (
        f"{name}: schema.json tools diverged from get_tools\n"
        f"  in schema but not resolved: {sorted(set(catalog_names) - set(resolved))}\n"
        f"  resolved but not in schema: {sorted(set(resolved) - set(catalog_names))}\n"
        f"Update the module's tool name map and schema.json together."
    )
