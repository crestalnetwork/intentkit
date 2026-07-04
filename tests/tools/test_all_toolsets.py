"""Smoke coverage across every toolset plugin (cheap net for wide refactors).

Imports each toolset under intentkit/tools/ and asserts it still exposes the
`get_tools` entrypoint, plus that its schema.json parses with the catalog
shape ({title, description, x-tags, tools: {name: {...}}}). One parametrized
test covers all ~50 plugins, including the many that have no dedicated test
file.
"""

import importlib
import json
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "intentkit" / "tools"


def _toolset_names():
    # Mirror the tool_registry contract: a toolset category is a directory
    # with a schema.json (shared infra packages like tools/mcp don't count).
    names = []
    for p in sorted(TOOLS_DIR.iterdir()):
        if p.is_dir() and (p / "schema.json").exists():
            names.append(p.name)
    return names


TOOLSETS = _toolset_names()


def test_toolsets_discovered():
    # Guard against an empty parametrization silently passing.
    assert len(TOOLSETS) >= 40, f"only found {len(TOOLSETS)} toolsets"


@pytest.mark.parametrize("name", TOOLSETS)
def test_toolset_imports_and_exposes_get_tools(name):
    mod = importlib.import_module(f"intentkit.tools.{name}")
    assert hasattr(mod, "get_tools"), (
        f"intentkit.tools.{name} is missing the get_tools entrypoint "
        f"(every toolset must resolve tool names to instances)"
    )
    assert callable(mod.get_tools)


@pytest.mark.parametrize("name", TOOLSETS)
def test_toolset_schema_parses(name):
    schema = TOOLS_DIR / name / "schema.json"
    data = json.loads(schema.read_text())
    tools = data.get("tools")
    assert isinstance(tools, dict) and tools, (
        f"{name}/schema.json must carry a non-empty 'tools' catalog map"
    )
    for tool_name, tool_def in tools.items():
        assert isinstance(tool_def, dict), (
            f"{name}/schema.json tools[{tool_name!r}] must be an object"
        )
