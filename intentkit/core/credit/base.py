from __future__ import annotations

import logging
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.credit import (
    CreditAccount,
    CreditEvent,
    CreditEventTable,
    OwnerType,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Define the precision for all decimal calculations (4 decimal places)
FOURPLACES = Decimal("0.0001")


class SkillCost(BaseModel):
    total_amount: Decimal
    base_amount: Decimal
    base_discount_amount: Decimal
    base_original_amount: Decimal
    base_skill_amount: Decimal
    fee_platform_amount: Decimal
    fee_dev_user: str
    fee_dev_user_type: OwnerType
    fee_dev_amount: Decimal
    fee_agent_amount: Decimal


async def update_credit_event_note(
    session: AsyncSession,
    event_id: str,
    note: str | None = None,
) -> CreditEvent:
    """
    Update the note of a credit event.

    Args:
        session: Async session to use for database operations
        event_id: ID of the event to update
        note: New note for the event

    Returns:
        Updated credit event

    Raises:
        HTTPException: If event is not found
    """
    # Find the event
    stmt = select(CreditEventTable).where(CreditEventTable.id == event_id)
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise IntentKitAPIError(
            status_code=404, key="CreditEventNotFound", message="Credit event not found"
        )

    # Update the note
    event.note = note
    await session.commit()
    await session.refresh(event)

    return CreditEvent.model_validate(event)


async def update_daily_quota(
    session: AsyncSession,
    user_id: str,
    free_quota: Decimal | None = None,
    refill_amount: Decimal | None = None,
    upstream_tx_id: str = "",
    note: str = "",
) -> CreditAccount:
    """
    Update the daily quota and refill amount of a user's credit account.

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to update
        free_quota: Optional new daily quota value
        refill_amount: Optional amount to refill hourly, not exceeding free_quota
        upstream_tx_id: ID of the upstream transaction (for logging purposes)
        note: Explanation for changing the daily quota

    Returns:
        Updated user credit account
    """
    return await CreditAccount.update_daily_quota(
        session, user_id, free_quota, refill_amount, upstream_tx_id, note
    )
