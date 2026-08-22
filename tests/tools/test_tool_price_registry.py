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


class TestMeteredCostRegistry:
    """The handoff that lets a tool bill what the provider actually charged.

    ``price`` is a class field and can only express a flat charge; metered
    tools report the provider's USD figure against their ``tool_call_id`` and
    core/engine/chunks.py spends that instead.
    """

    def setup_method(self):
        tool_base._metered_tool_costs.clear()

    teardown_method = setup_method

    def test_cost_is_consumed_once(self):
        """The cost belongs to exactly one credit event."""
        tool_base.report_tool_cost_usd("call-once", Decimal("0.5"))
        assert tool_base.take_tool_cost_usd("call-once") == Decimal("0.5")
        assert tool_base.take_tool_cost_usd("call-once") is None

    def test_unreported_call_is_not_metered(self):
        assert tool_base.take_tool_cost_usd("never-reported") is None

    def test_repeat_reports_accumulate(self):
        """ToolRetryMiddleware reuses the tool_call_id across attempts, and a
        retry that reached the provider was charged for separately — so the
        call owes the sum, not just the last attempt."""
        tool_base.report_tool_cost_usd("call-retried", Decimal("0.25"))
        tool_base.report_tool_cost_usd("call-retried", Decimal("0.25"))
        assert tool_base.take_tool_cost_usd("call-retried") == Decimal("0.50")

    def test_missing_call_id_is_dropped(self):
        tool_base.report_tool_cost_usd(None, Decimal("0.5"))
        assert not tool_base._metered_tool_costs

    def test_registry_is_bounded(self):
        """A run cancelled between the tool returning and billing never drains
        its entry, so the registry must not grow without limit."""
        limit = tool_base._METERED_COST_LIMIT
        for i in range(limit + 10):
            tool_base.report_tool_cost_usd(f"leak-{i}", Decimal("1"))
        assert len(tool_base._metered_tool_costs) == limit
        # Oldest evicted, newest kept.
        assert tool_base.take_tool_cost_usd("leak-0") is None
        assert tool_base.take_tool_cost_usd(f"leak-{limit + 9}") == Decimal("1")
