"""Guard: per-tool ``available()`` overrides must reach the catalog layer.

Runtime binding always honors ``available()`` (executor filters instances),
but the catalog/UI path resolves instances indirectly — historically only
through the optional ``get_<category>_tool`` getter, which silently ignored
overrides in categories without one. This test asserts that for EVERY
cataloged tool whose class overrides ``available()``, the catalog-layer check
returns exactly what the instance reports — so an override can never be
silently ignored again.
"""

import pytest

from intentkit.core.agent.tool_registry import get_tool_catalog
from intentkit.tools.availability import is_individual_tool_available
from intentkit.tools.base import (
    IntentKitTool,
    get_tool_instance,
    tool_classes_by_name,
)


def _override_cases() -> list[tuple[str, str]]:
    classes = tool_classes_by_name()
    cases = []
    for category, payload in get_tool_catalog().items():
        for tool_name in payload["tools"]:
            cls = classes.get(tool_name)
            if cls is None:
                continue  # MCP single-entry catalogs have no backing class
            if cls.available is not IntentKitTool.available:
                cases.append((category, tool_name))
    return cases


def test_override_cases_exist():
    # image/video tools override available(); if this ever hits zero the
    # parametrized test below silently vanishes.
    assert len(_override_cases()) > 0


def test_every_cataloged_class_is_instantiable():
    """A tool class the registry knows must construct: a broken constructor
    would silently drop its available() override from the catalog check."""
    classes = tool_classes_by_name()
    for category, payload in get_tool_catalog().items():
        for tool_name in payload["tools"]:
            if tool_name in classes:
                assert get_tool_instance(tool_name) is not None, (
                    f"{category}/{tool_name} failed to instantiate"
                )


@pytest.mark.parametrize("category,tool_name", _override_cases())
def test_available_override_reaches_catalog_layer(category, tool_name):
    instance = get_tool_instance(tool_name)
    assert instance is not None
    assert is_individual_tool_available(category, tool_name) == bool(
        instance.available()
    )


def test_getterless_category_honors_override(monkeypatch):
    """erc20 exposes no tool getter; before the class-registry resolution its
    per-tool overrides were silently ignored by the catalog layer."""
    from intentkit.tools.erc20.get_balance import ERC20GetBalance

    assert is_individual_tool_available("erc20", "erc20_get_balance") is True

    monkeypatch.setattr(ERC20GetBalance, "available", lambda self: False)
    assert is_individual_tool_available("erc20", "erc20_get_balance") is False
