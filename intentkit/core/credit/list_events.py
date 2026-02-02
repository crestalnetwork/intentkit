from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.credit import (
    CreditAccount,
    CreditEvent,
    CreditEventTable,
    Direction,
    EventType,
    OwnerType,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def list_credit_events_by_user(
    session: AsyncSession,
    user_id: str,
    direction: Direction | None = None,
    cursor: str | None = None,
    limit: int = 20,
    event_type: EventType | None = None,
) -> tuple[list[CreditEvent], str | None, bool]:
    """
    List credit events for a user account with cursor pagination.

    Args:
        session: Async database session.
        user_id: The ID of the user.
        direction: The direction of the events (INCOME or EXPENSE).
        cursor: The ID of the last event from the previous page.
        limit: Maximum number of events to return per page.
        event_type: Optional filter for specific event type.

    Returns:
        A tuple containing:
        - A list of CreditEvent models.
        - The cursor for the next page (ID of the last event in the list).
        - A boolean indicating if there are more events available.
    """
    # 1. Find the account for the owner
    account = await CreditAccount.get_in_session(session, OwnerType.USER, user_id)
    if not account:
        # Decide if returning empty or raising error is better. Empty list seems reasonable.
        # Or raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{owner_type.value.capitalize()} account not found")
        return [], None, False

    # 2. Build the query
    stmt = (
        select(CreditEventTable)
        .where(CreditEventTable.account_id == account.id)
        .order_by(desc(CreditEventTable.id))
        .limit(limit + 1)  # Fetch one extra to check if there are more
    )

    # 3. Apply optional filter if provided
    if direction:
        stmt = stmt.where(CreditEventTable.direction == direction.value)
    if event_type:
        stmt = stmt.where(CreditEventTable.event_type == event_type.value)

    # 4. Apply cursor filter if provided
    if cursor:
        stmt = stmt.where(CreditEventTable.id < cursor)

    # 5. Execute query
    result = await session.execute(stmt)
    events_data = result.scalars().all()

    # 6. Determine pagination details
    has_more = len(events_data) > limit
    events_to_return = events_data[:limit]  # Slice to the requested limit

    next_cursor = events_to_return[-1].id if events_to_return and has_more else None

    # 7. Convert to Pydantic models
    events_models = [CreditEvent.model_validate(event) for event in events_to_return]

    return events_models, next_cursor, has_more


async def list_credit_events(
    session: AsyncSession,
    direction: Direction | None = Direction.EXPENSE,
    cursor: str | None = None,
    limit: int = 20,
    event_type: EventType | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[list[CreditEvent], str | None, bool]:
    """
    List all credit events with cursor pagination.

    Args:
        session: Async database session.
        direction: The direction of the events (INCOME or EXPENSE). Default is EXPENSE.
        cursor: The ID of the last event from the previous page.
        limit: Maximum number of events to return per page.
        event_type: Optional filter for specific event type.
        start_at: Optional start datetime to filter events by created_at.
        end_at: Optional end datetime to filter events by created_at.

    Returns:
        A tuple containing:
        - A list of CreditEvent models.
        - The cursor for the next page (ID of the last event in the list).
        - A boolean indicating if there are more events available.
    """
    # Build the query
    stmt = (
        select(CreditEventTable)
        .order_by(CreditEventTable.id)  # Ascending order as required
        .limit(limit + 1)  # Fetch one extra to check if there are more
    )

    # Apply direction filter (default is EXPENSE)
    if direction:
        stmt = stmt.where(CreditEventTable.direction == direction.value)

    # Apply optional event_type filter if provided
    if event_type:
        stmt = stmt.where(CreditEventTable.event_type == event_type.value)

    # Apply datetime filters if provided
    if start_at:
        stmt = stmt.where(CreditEventTable.created_at >= start_at)
    if end_at:
        stmt = stmt.where(CreditEventTable.created_at < end_at)

    # Apply cursor filter if provided
    if cursor:
        stmt = stmt.where(CreditEventTable.id > cursor)  # Using > for ascending order

    # Execute query
    result = await session.execute(stmt)
    events_data = result.scalars().all()

    # Determine pagination details
    has_more = len(events_data) > limit
    events_to_return = events_data[:limit]  # Slice to the requested limit

    # always return a cursor even there is no next page
    next_cursor = events_to_return[-1].id if events_to_return else None

    # Convert to Pydantic models
    events_models = [CreditEvent.model_validate(event) for event in events_to_return]

    return events_models, next_cursor, has_more


async def list_fee_events_by_agent(
    session: AsyncSession,
    agent_id: str,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[CreditEvent], str | None, bool]:
    """
    List fee events for an agent with cursor pagination.
    These events represent income for the agent from users' expenses.

    Args:
        session: Async database session.
        agent_id: The ID of the agent.
        cursor: The ID of the last event from the previous page.
        limit: Maximum number of events to return per page.

    Returns:
        A tuple containing:
        - A list of CreditEvent models.
        - The cursor for the next page (ID of the last event in the list).
        - A boolean indicating if there are more events available.
    """
    # 1. Find the account for the agent
    agent_account = await CreditAccount.get_in_session(
        session, OwnerType.AGENT, agent_id
    )
    if not agent_account:
        return [], None, False

    # 2. Build the query to find events where fee_agent_amount > 0 and fee_agent_account = agent_account.id
    stmt = (
        select(CreditEventTable)
        .where(CreditEventTable.fee_agent_account == agent_account.id)
        .where(CreditEventTable.fee_agent_amount > 0)
        .order_by(desc(CreditEventTable.id))
        .limit(limit + 1)  # Fetch one extra to check if there are more
    )

    # 3. Apply cursor filter if provided
    if cursor:
        stmt = stmt.where(CreditEventTable.id < cursor)

    # 4. Execute query
    result = await session.execute(stmt)
    events_data = result.scalars().all()

    # 5. Determine pagination details
    has_more = len(events_data) > limit
    events_to_return = events_data[:limit]  # Slice to the requested limit

    next_cursor = events_to_return[-1].id if events_to_return and has_more else None

    # 6. Convert to Pydantic models
    events_models = [CreditEvent.model_validate(event) for event in events_to_return]

    return events_models, next_cursor, has_more


async def fetch_credit_event_by_upstream_tx_id(
    session: AsyncSession,
    upstream_tx_id: str,
) -> CreditEvent:
    """
    Fetch a credit event by its upstream transaction ID.

    Args:
        session: Async database session.
        upstream_tx_id: ID of the upstream transaction.

    Returns:
        The credit event if found.

    Raises:
        HTTPException: If the credit event is not found.
    """
    # Build the query to find the event by upstream_tx_id
    stmt = select(CreditEventTable).where(
        CreditEventTable.upstream_tx_id == upstream_tx_id
    )

    # Execute query
    result = await session.scalar(stmt)

    # Raise 404 if not found
    if not result:
        raise IntentKitAPIError(
            status_code=404,
            key="CreditEventNotFound",
            message=f"Credit event with upstream_tx_id '{upstream_tx_id}' not found",
        )

    # Convert to Pydantic model and return
    return CreditEvent.model_validate(result)


async def fetch_credit_event_by_id(
    session: AsyncSession,
    event_id: str,
) -> CreditEvent:
    """
    Fetch a credit event by its ID.

    Args:
        session: Async database session.
        event_id: ID of the credit event.

    Returns:
        The credit event if found.

    Raises:
        IntentKitAPIError: If the credit event is not found.
    """
    # Build the query to find the event by ID
    stmt = select(CreditEventTable).where(CreditEventTable.id == event_id)

    # Execute query
    result = await session.scalar(stmt)

    # Raise 404 if not found
    if not result:
        raise IntentKitAPIError(
            status_code=404,
            key="CreditEventNotFound",
            message=f"Credit event with ID '{event_id}' not found",
        )

    # Convert to Pydantic model and return
    return CreditEvent.model_validate(result)
