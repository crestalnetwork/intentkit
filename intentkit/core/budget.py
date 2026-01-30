"""Hourly budget helpers backed by Redis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

from intentkit.config.config import config
from intentkit.config.redis import get_redis

KEY_PREFIX: Final[str] = "intentkit:budget:hourly"


@dataclass(frozen=True)
class HourlyBudgetResult:
    exceeded: bool
    current_total: Decimal
    budget: Decimal | None


def _current_hour_key(scope: str) -> str:
    now = datetime.now(UTC)
    hour_key = now.strftime("%Y%m%d%H")
    return f"{KEY_PREFIX}:{scope}:{hour_key}"


def _seconds_until_next_hour() -> int:
    now = datetime.now(UTC)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    delta = next_hour - now
    return max(int(delta.total_seconds()), 1)


async def accumulate_hourly_base_llm_amount(
    scope: str,
    amount: Decimal,
) -> Decimal:
    """Accumulate base LLM amount for the current hour and return total."""
    redis = get_redis()
    key = _current_hour_key(scope)

    # Use incrbyfloat for better precision with small amounts
    # Redis incrbyfloat returns float
    ttl_seconds = _seconds_until_next_hour()
    total_float = await redis.incrbyfloat(key, float(amount))
    await redis.expire(key, ttl_seconds)

    return Decimal(str(total_float))


async def check_hourly_budget_exceeded(scope: str) -> HourlyBudgetResult:
    """Check whether the current hour total exceeds the configured budget."""
    budget = config.hourly_budget
    if budget is None:
        return HourlyBudgetResult(
            exceeded=False, current_total=Decimal("0"), budget=None
        )
    redis = get_redis()
    key = _current_hour_key(scope)
    current_raw = await redis.get(key)
    current_total = Decimal(str(current_raw)) if current_raw else Decimal("0")
    exceeded = current_total > budget
    return HourlyBudgetResult(
        exceeded=exceeded,
        current_total=current_total,
        budget=budget,
    )
