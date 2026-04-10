"""Tests for TeamPlan and PLAN_CONFIGS."""

from decimal import Decimal

from intentkit.models.team import PLAN_CONFIGS, TeamPlan


def test_all_plans_have_configs():
    for plan in TeamPlan:
        assert plan in PLAN_CONFIGS, f"Missing config for plan {plan}"


def test_none_plan_all_zeros():
    cfg = PLAN_CONFIGS[TeamPlan.NONE]
    assert cfg.free_quota == Decimal("0")
    assert cfg.refill_amount == Decimal("0")
    assert cfg.monthly_permanent_credits == Decimal("0")


def test_free_plan():
    cfg = PLAN_CONFIGS[TeamPlan.FREE]
    assert cfg.free_quota == Decimal("50")
    assert cfg.refill_amount == Decimal("10")
    assert cfg.monthly_permanent_credits == Decimal("0")


def test_pro_plan():
    cfg = PLAN_CONFIGS[TeamPlan.PRO]
    assert cfg.free_quota == Decimal("1000")
    assert cfg.refill_amount == Decimal("500")
    assert cfg.monthly_permanent_credits == Decimal("10000")
    assert cfg.seats == 3
    assert cfg.month_price_cents == 1900
    assert cfg.year_price_cents == 19000


def test_max_plan():
    cfg = PLAN_CONFIGS[TeamPlan.MAX]
    assert cfg.free_quota == Decimal("10000")
    assert cfg.refill_amount == Decimal("5000")
    assert cfg.monthly_permanent_credits == Decimal("100000")
    assert cfg.seats == 15
    assert cfg.month_price_cents == 19900
    assert cfg.year_price_cents == 199000


def test_plan_enum_values():
    assert TeamPlan.NONE.value == "none"
    assert TeamPlan.FREE.value == "free"
    assert TeamPlan.PRO.value == "pro"
    assert TeamPlan.MAX.value == "max"
