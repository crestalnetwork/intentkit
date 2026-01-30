from decimal import Decimal

import pytest

import intentkit.core.budget as budget_module
from intentkit.core.budget import (
    accumulate_hourly_base_llm_amount,
    check_hourly_budget_exceeded,
)


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, float] = {}

    async def incrbyfloat(self, key: str, amount: float) -> float:
        current = self.storage.get(key, 0.0)
        new_value = current + amount
        self.storage[key] = new_value
        return new_value

    async def get(self, key: str) -> str | None:
        value = self.storage.get(key)
        return str(value) if value is not None else None

    async def expire(self, key: str, seconds: int) -> bool:
        _ = key
        _ = seconds
        return True


@pytest.mark.asyncio
async def test_hourly_budget_exceeded_on_second_request(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(budget_module, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(budget_module.config, "hourly_budget", Decimal("0.0001"))

    scope = "base_llm:user-1"

    pre_first = await check_hourly_budget_exceeded(scope)
    assert not pre_first.exceeded

    await accumulate_hourly_base_llm_amount(scope, Decimal("0.0002"))

    pre_second = await check_hourly_budget_exceeded(scope)
    assert pre_second.exceeded
    assert pre_second.current_total == Decimal("0.0002")
    assert pre_second.budget == Decimal("0.0001")


@pytest.mark.asyncio
async def test_hourly_budget_disabled_when_none(monkeypatch):
    """When hourly_budget is None, budget check should always pass."""
    fake_redis = FakeRedis()
    monkeypatch.setattr(budget_module, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(budget_module.config, "hourly_budget", None)

    scope = "base_llm:user-2"

    # Accumulate a large amount
    await accumulate_hourly_base_llm_amount(scope, Decimal("1000000"))

    # Should never be exceeded when budget is None
    result = await check_hourly_budget_exceeded(scope)
    assert not result.exceeded
    assert result.budget is None
    assert result.current_total == Decimal("0")


@pytest.mark.asyncio
async def test_hourly_budget_not_exceeded_at_boundary(monkeypatch):
    """When current_total equals budget exactly, should NOT be exceeded."""
    fake_redis = FakeRedis()
    monkeypatch.setattr(budget_module, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(budget_module.config, "hourly_budget", Decimal("0.0001"))

    scope = "base_llm:user-3"

    # Accumulate exactly the budget amount
    await accumulate_hourly_base_llm_amount(scope, Decimal("0.0001"))

    result = await check_hourly_budget_exceeded(scope)
    # Exactly at budget should NOT be exceeded (uses > not >=)
    assert not result.exceeded
    assert result.current_total == Decimal("0.0001")
    assert result.budget == Decimal("0.0001")


@pytest.mark.asyncio
async def test_hourly_budget_exceeded_just_over_boundary(monkeypatch):
    """When current_total is just over budget, should be exceeded."""
    fake_redis = FakeRedis()
    monkeypatch.setattr(budget_module, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(budget_module.config, "hourly_budget", Decimal("0.0001"))

    scope = "base_llm:user-4"

    # Accumulate slightly more than budget
    await accumulate_hourly_base_llm_amount(scope, Decimal("0.00010001"))

    result = await check_hourly_budget_exceeded(scope)
    assert result.exceeded
    assert result.current_total > result.budget
