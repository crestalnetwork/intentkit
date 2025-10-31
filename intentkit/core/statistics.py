"""Agent statistics utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.agent_data import AgentQuota, AgentQuotaTable
from intentkit.models.credit import CreditAccount, CreditEventTable, OwnerType
from intentkit.models.db import get_session


class AgentStatistics(BaseModel):
    """Aggregated statistics for an agent credit account."""

    agent_id: str = Field(description="ID of the agent")
    account_id: str = Field(description="ID of the associated credit account")
    balance: Decimal = Field(description="Current credit account balance")
    total_income: Decimal = Field(description="Total income across all events")
    net_income: Decimal = Field(description="Net income from fee allocations")
    permanent_income: Decimal = Field(
        description="Total permanent income across all events"
    )
    permanent_profit: Decimal = Field(
        description="Permanent profit allocated to the agent"
    )
    last_24h_income: Decimal = Field(
        description="Income generated during the last 24 hours"
    )
    last_24h_permanent_income: Decimal = Field(
        description="Permanent income generated during the last 24 hours"
    )
    avg_action_cost: Decimal = Field(description="Average action cost")
    min_action_cost: Decimal = Field(description="Minimum action cost")
    max_action_cost: Decimal = Field(description="Maximum action cost")
    low_action_cost: Decimal = Field(description="20th percentile action cost")
    medium_action_cost: Decimal = Field(description="60th percentile action cost")
    high_action_cost: Decimal = Field(description="80th percentile action cost")


async def get_agent_statistics(
    agent_id: str,
    *,
    end_time: datetime | None = None,
    session: AsyncSession | None = None,
) -> AgentStatistics:
    """Calculate statistics for an agent credit account.

    Args:
        agent_id: ID of the agent.
        end_time: Optional end time used as the inclusive boundary for
            time-windowed aggregations. Defaults to the current UTC time.
        session: Optional database session to reuse. When omitted, a
            standalone session will be created and committed automatically.

    Returns:
        Aggregated statistics for the agent.
    """

    managed_session = session is None
    if end_time is None:
        end_time = datetime.now(UTC)
    elif end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=UTC)
    else:
        end_time = end_time.astimezone(UTC)

    async def _compute(session: AsyncSession) -> AgentStatistics:
        account = await CreditAccount.get_or_create_in_session(
            session, OwnerType.AGENT, agent_id
        )
        balance = account.free_credits + account.reward_credits + account.credits

        totals_stmt = select(
            func.sum(CreditEventTable.total_amount).label("total_income"),
            func.sum(CreditEventTable.fee_agent_amount).label("net_income"),
            func.sum(CreditEventTable.permanent_amount).label("permanent_income"),
            func.sum(CreditEventTable.fee_agent_permanent_amount).label(
                "permanent_profit"
            ),
        ).where(CreditEventTable.agent_id == agent_id)
        totals_result = await session.execute(totals_stmt)
        totals_row = totals_result.first()

        total_income = (
            totals_row.total_income
            if totals_row and totals_row.total_income
            else Decimal("0")
        )
        net_income = (
            totals_row.net_income
            if totals_row and totals_row.net_income
            else Decimal("0")
        )
        permanent_income = (
            totals_row.permanent_income
            if totals_row and totals_row.permanent_income
            else Decimal("0")
        )
        permanent_profit = (
            totals_row.permanent_profit
            if totals_row and totals_row.permanent_profit
            else Decimal("0")
        )

        window_start = end_time - timedelta(hours=24)
        window_stmt = select(
            func.sum(CreditEventTable.total_amount).label("last_24h_income"),
            func.sum(CreditEventTable.permanent_amount).label(
                "last_24h_permanent_income"
            ),
        ).where(
            CreditEventTable.agent_id == agent_id,
            CreditEventTable.created_at >= window_start,
            CreditEventTable.created_at <= end_time,
        )
        window_result = await session.execute(window_stmt)
        window_row = window_result.first()

        last_24h_income = (
            window_row.last_24h_income
            if window_row and window_row.last_24h_income
            else Decimal("0")
        )
        last_24h_permanent_income = (
            window_row.last_24h_permanent_income
            if window_row and window_row.last_24h_permanent_income
            else Decimal("0")
        )

        quota_row = await session.get(AgentQuotaTable, agent_id)
        quota = (
            AgentQuota.model_validate(quota_row)
            if quota_row
            else AgentQuota(id=agent_id)
        )

        return AgentStatistics(
            agent_id=agent_id,
            account_id=account.id,
            balance=balance,
            total_income=total_income,
            net_income=net_income,
            permanent_income=permanent_income,
            permanent_profit=permanent_profit,
            last_24h_income=last_24h_income,
            last_24h_permanent_income=last_24h_permanent_income,
            avg_action_cost=quota.avg_action_cost,
            min_action_cost=quota.min_action_cost,
            max_action_cost=quota.max_action_cost,
            low_action_cost=quota.low_action_cost,
            medium_action_cost=quota.medium_action_cost,
            high_action_cost=quota.high_action_cost,
        )

    if managed_session:
        async with get_session() as managed:
            statistics = await _compute(managed)
            await managed.commit()
            return statistics
    return await _compute(session)


__all__ = ["AgentStatistics", "get_agent_statistics"]
