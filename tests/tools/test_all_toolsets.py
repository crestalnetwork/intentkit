"""Smoke coverage across every toolset plugin (cheap net for wide refactors).

Imports each package under intentkit/tools/ and asserts the toolset contract:
anything that resolves tools (``get_tools``) must declare its catalog metadata
(a module-level ``toolset`` ToolsetMeta) and vice versa. One parametrized test
covers all ~50 plugins, including the many that have no dedicated test file.
"""

import importlib
import pkgutil

import pytest

import intentkit.tools as tools_pkg
from intentkit.tools.meta import ToolsetMeta

PACKAGES = sorted(m.name for m in pkgutil.iter_modules(tools_pkg.__path__) if m.ispkg)


def test_toolsets_discovered():
    # Guard against an empty parametrization silently passing.
    count = 0
    for name in PACKAGES:
        mod = importlib.import_module(f"intentkit.tools.{name}")
        if isinstance(getattr(mod, "toolset", None), ToolsetMeta):
            count += 1
    assert count >= 40, f"only found {count} toolsets"


@pytest.mark.parametrize("name", PACKAGES)
def test_toolset_contract(name):
    mod = importlib.import_module(f"intentkit.tools.{name}")
    meta = getattr(mod, "toolset", None)
    has_get_tools = callable(getattr(mod, "get_tools", None))

    if meta is None and not has_get_tools:
        # Shared infra package (e.g. tools/mcp), not a toolset category.
        return

    assert isinstance(meta, ToolsetMeta), (
        f"intentkit.tools.{name} resolves tools but declares no `toolset` "
        f"ToolsetMeta — it would be invisible to the catalog"
    )
    assert has_get_tools, (
        f"intentkit.tools.{name} declares a toolset meta but is missing the "
        f"get_tools entrypoint (every toolset must resolve tool names)"
    )
    assert meta.title, f"{name}: toolset title must not be empty"
    assert meta.description, f"{name}: toolset description must not be empty"
    assert isinstance(meta.tags, list)
