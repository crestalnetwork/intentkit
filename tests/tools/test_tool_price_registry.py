"""Regression tests for the global tool price registry."""

from decimal import Decimal

from intentkit.tools import base as tool_base
from intentkit.tools.base import IntentKitTool, build_tool_prices, get_tool_price


class _DummyPricedTool(IntentKitTool):  # pyright: ignore[reportUnusedClass]
    """Test-only tool with a sentinel price that won't collide with real tools."""

    name: str = "_dummy_priced_tool_for_test"
    description: str = "test fixture"
    category: str = "_test"
    price: Decimal = Decimal("999.5")

    async def _arun(self, **_: object) -> str:
        return ""


def _rebuild_registry() -> None:
    """Force a clean rebuild of the global price registry."""
    tool_base._TOOL_PRICES.clear()
    tool_base._registry_built = False
    # The class map is cached per process; test-only classes defined above
    # must become visible to this rebuild.
    tool_base.tool_classes_by_name.cache_clear()
    build_tool_prices()


def test_registry_is_populated():
    _rebuild_registry()
    assert len(tool_base._TOOL_PRICES) > 0, (
        "Tool price registry is empty — tools will all be charged the fallback "
        "instead of their declared prices."
    )


def test_dummy_tool_price_is_registered():
    """Proves the mechanism: a Pydantic field default becomes the registered price."""
    _rebuild_registry()
    assert get_tool_price("_dummy_priced_tool_for_test") == Decimal("999.5")


def test_real_tools_match_their_field_defaults():
    """Every registered tool's price must equal its class `price` field default."""
    _rebuild_registry()
    for cls in tool_base._collect_subclasses(IntentKitTool):
        name = cls.model_fields["name"].default
        if not isinstance(name, str) or not name:
            continue
        expected = cls.model_fields["price"].default
        assert get_tool_price(name) == expected, (
            f"{cls.__name__}({name!r}) registered price differs from field default"
        )


def test_unknown_tool_falls_back_to_default():
    _rebuild_registry()
    assert get_tool_price("definitely_not_a_real_tool_name_xyz") == Decimal("1")
