import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.core import statistics as agent_statistics
from intentkit.core.credit import (
    fetch_credit_event_by_id,
    fetch_credit_event_by_upstream_tx_id,
    list_credit_events,
    list_credit_events_by_user,
    list_fee_events_by_agent,
    recharge,
    reward,
    update_credit_event_note,
    update_daily_quota,
    withdraw,
)
from intentkit.models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditDebit,
    CreditEvent,
    CreditEventTable,
    CreditTransaction,
    CreditTransactionTable,
    Direction,
    EventType,
    OwnerType,
    RewardType,
    TransactionType,
)
from intentkit.models.db import get_db
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

credit_router = APIRouter(prefix="/credit", tags=["Credit"])


# ===== Models =====
class CreditEventsResponse(BaseModel):
    """Response model for credit events with pagination."""

    data: list[CreditEvent] = Field(description="List of credit events")
    has_more: bool = Field(description="Indicates if there are more items")
    next_cursor: str | None = Field(None, description="Cursor for next page")


class CreditTransactionResp(CreditTransaction):
    """Credit transaction response model with event data."""

    event: CreditEvent | None = Field(None, description="Associated credit event")


class CreditTransactionsResponse(BaseModel):
    """Response model for credit transactions with pagination."""

    data: list[CreditTransactionResp] = Field(description="List of credit transactions")
    has_more: bool = Field(description="Indicates if there are more items")
    next_cursor: str | None = Field(None, description="Cursor for next page")


# ===== Input models =====
class RechargeRequest(BaseModel):
    """Request model for recharging a user account."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    user_id: Annotated[str, Field(description="ID of the user to recharge")]
    amount: Annotated[Decimal, Field(gt=Decimal("0"), description="Amount to recharge")]
    note: Annotated[
        str | None, Field(None, description="Optional note for the recharge")
    ]


class RewardRequest(BaseModel):
    """Request model for rewarding a user account."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    user_id: Annotated[str, Field(description="ID of the user to reward")]
    amount: Annotated[Decimal, Field(gt=Decimal("0"), description="Amount to reward")]
    note: Annotated[str | None, Field(None, description="Optional note for the reward")]
    reward_type: Annotated[
        RewardType | None,
        Field(RewardType.REWARD, description="Type of reward event"),
    ]


class WithdrawRequest(BaseModel):
    """Request model for withdrawing from an agent account."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    agent_id: Annotated[str, Field(description="ID of the agent to withdraw from")]
    amount: Annotated[Decimal, Field(gt=Decimal("0"), description="Amount to withdraw")]
    note: Annotated[
        str | None, Field(None, description="Optional note for the withdraw")
    ]


# class AdjustmentRequest(BaseModel):
#     """Request model for adjusting a user account."""

#     upstream_tx_id: Annotated[
#         str, Field(str, description="Upstream transaction ID, idempotence Check")
#     ]
#     user_id: Annotated[str, Field(description="ID of the user to adjust")]
#     credit_type: Annotated[CreditType, Field(description="Type of credit to adjust")]
#     amount: Annotated[
#         Decimal, Field(description="Amount to adjust (positive or negative)")
#     ]
#     note: Annotated[str, Field(description="Required explanation for the adjustment")]


class UpdateDailyQuotaRequest(BaseModel):
    """Request model for updating account daily quota and refill amount."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    free_quota: Annotated[
        Decimal | None,
        Field(
            None, gt=Decimal("0"), description="New daily quota value for the account"
        ),
    ]
    refill_amount: Annotated[
        Decimal | None,
        Field(
            None,
            ge=Decimal("0"),
            description="Amount to refill hourly, not exceeding free_quota",
        ),
    ]
    note: Annotated[
        str,
        Field(description="Explanation for changing the daily quota and refill amount"),
    ]

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateDailyQuotaRequest":
        """Validate that at least one of free_quota or refill_amount is provided."""
        if self.free_quota is None and self.refill_amount is None:
            raise ValueError(
                "At least one of free_quota or refill_amount must be provided"
            )
        return self


class UpdateEventNoteRequest(BaseModel):
    """Request model for updating event note."""

    note: Annotated[str | None, Field(None, description="New note for the event")]


# ===== API Endpoints =====
@credit_router.get(
    "/accounts/{owner_type}/{owner_id}",
    response_model=CreditAccount,
    operation_id="get_account",
    summary="Get Account",
)
async def get_account(owner_type: OwnerType, owner_id: str) -> CreditAccount:
    """Get a credit account by owner type and ID. It will create a new account if it does not exist.

    This endpoint is not in readonly router, because it may create a new account.

    Args:
        owner_type: Type of the owner (user, agent, company)
        owner_id: ID of the owner

    Returns:
        The credit account
    """
    return await CreditAccount.get_or_create(owner_type, owner_id)


@credit_router.post(
    "/recharge",
    response_model=CreditAccount,
    status_code=status.HTTP_201_CREATED,
    operation_id="recharge_account",
    summary="Recharge",
)
async def recharge_user_account(
    request: RechargeRequest,
    db: AsyncSession = Depends(get_db),
) -> CreditAccount:
    """Recharge a user account with credits.

    Args:
        request: Recharge request details

    Returns:
        The updated credit account
    """
    return await recharge(
        db, request.user_id, request.amount, request.upstream_tx_id, request.note
    )


@credit_router.post(
    "/reward",
    response_model=CreditAccount,
    status_code=status.HTTP_201_CREATED,
    operation_id="reward_account",
    summary="Reward",
)
async def reward_user_account(
    request: RewardRequest,
    db: AsyncSession = Depends(get_db),
) -> CreditAccount:
    """Reward a user account with credits.

    Args:
        request: Reward request details
        db: Database session

    Returns:
        The updated credit account
    """
    return await reward(
        db,
        request.user_id,
        request.amount,
        request.upstream_tx_id,
        request.note,
        request.reward_type,
    )


@credit_router.post(
    "/withdraw",
    response_model=CreditAccount,
    status_code=status.HTTP_201_CREATED,
    operation_id="withdraw_account",
    summary="Withdraw",
)
async def withdraw_agent_account(
    request: WithdrawRequest,
    db: AsyncSession = Depends(get_db),
) -> CreditAccount:
    """Withdraw credits from an agent account to platform account.

    Args:
        request: Withdraw request details
        db: Database session

    Returns:
        The updated agent credit account
    """
    return await withdraw(
        db, request.agent_id, request.amount, request.upstream_tx_id, request.note
    )


# @credit_router.post(
#     "/adjust",
#     response_model=CreditAccount,
#     status_code=status.HTTP_201_CREATED,
#     operation_id="adjust_account",
#     summary="Adjust",
# )
# async def adjust_user_account(
#     request: AdjustmentRequest,
#     db: AsyncSession = Depends(get_db),
# ) -> CreditAccount:
#     """Adjust a user account's credits.

#     Args:
#         request: Adjustment request details
#         db: Database session

#     Returns:
#         The updated credit account
#     """
#     return await adjustment(
#         db,
#         request.user_id,
#         request.credit_type,
#         request.amount,
#         request.upstream_tx_id,
#         request.note,
#     )


@credit_router.put(
    "/accounts/users/{user_id}/daily-quota",
    response_model=CreditAccount,
    status_code=status.HTTP_200_OK,
    operation_id="update_account_free_quota",
    summary="Update Daily Quota and Refill Amount",
)
async def update_account_free_quota(
    user_id: str, request: UpdateDailyQuotaRequest, db: AsyncSession = Depends(get_db)
) -> CreditAccount:
    """Update the daily quota and refill amount of a credit account.

    Args:
        user_id: ID of the user
        request: Update request details including optional free_quota, optional refill_amount, and explanation note
        db: Database session

    Returns:
        The updated credit account
    """
    # At least one of free_quota or refill_amount must be provided (validated in the request model)
    return await update_daily_quota(
        session=db,
        user_id=user_id,
        free_quota=request.free_quota,
        refill_amount=request.refill_amount,
        upstream_tx_id=request.upstream_tx_id,
        note=request.note,
    )


@credit_router.get(
    "/accounts/agent/{agent_id}/statistics",
    response_model=agent_statistics.AgentStatistics,
    operation_id="get_agent_statistics",
    summary="Get Agent Statistics",
)
async def get_agent_statistics(
    agent_id: Annotated[str, Path(description="ID of the agent")],
    db: AsyncSession = Depends(get_db),
) -> agent_statistics.AgentStatistics:
    """Get statistics for an agent account.

    This endpoint is not in readonly router, because it may create a new account.

    Args:
        agent_id: ID of the agent
        db: Database session

    Returns:
        Agent statistics including balance, total income, and net income

    Raises:
        404: If the agent account is not found
    """
    return await agent_statistics.get_agent_statistics(agent_id, session=db)


@credit_router.get(
    "/users/{user_id}/events",
    response_model=CreditEventsResponse,
    operation_id="list_user_events",
    summary="List User Events",
)
async def list_user_events(
    user_id: str,
    event_type: Annotated[EventType | None, Query(description="Event type")] = None,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreditEventsResponse:
    """List all events for a user account with optional event type filtering.

    Args:
        user_id: ID of the user
        event_type: Optional filter for specific event type
        cursor: Cursor for pagination
        limit: Maximum number of events to return
        db: Database session

    Returns:
        Response with list of events and pagination information
    """
    events, next_cursor, has_more = await list_credit_events_by_user(
        session=db,
        user_id=user_id,
        cursor=cursor,
        limit=limit,
        event_type=event_type,
    )

    return CreditEventsResponse(
        data=events,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@credit_router.patch(
    "/events/{event_id}",
    response_model=CreditEvent,
    operation_id="update_event_note",
    summary="Update Event Note",
)
async def update_event_note(
    event_id: Annotated[str, Path(description="ID of the event to update")],
    request: UpdateEventNoteRequest,
    db: AsyncSession = Depends(get_db),
) -> CreditEvent:
    """Update the note of a credit event.

    Args:
        event_id: ID of the event to update
        request: Request containing the new note
        db: Database session

    Returns:
        The updated credit event

    Raises:
        404: If the event is not found
    """
    return await update_credit_event_note(
        session=db,
        event_id=event_id,
        note=request.note,
    )


@credit_router.get(
    "/event/users/{user_id}/expense",
    response_model=CreditEventsResponse,
    operation_id="list_user_expense_events",
    summary="List User Expense",
)
async def list_user_expense_events(
    user_id: str,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreditEventsResponse:
    """List all expense events for a user account.

    Args:
        user_id: ID of the user
        cursor: Cursor for pagination
        limit: Maximum number of events to return
        db: Database session

    Returns:
        Response with list of expense events and pagination information
    """
    events, next_cursor, has_more = await list_credit_events_by_user(
        session=db,
        user_id=user_id,
        direction=Direction.EXPENSE,
        cursor=cursor,
        limit=limit,
    )

    return CreditEventsResponse(
        data=events,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@credit_router.get(
    "/transactions",
    response_model=CreditTransactionsResponse,
    operation_id="list_transactions",
    summary="List Transactions",
)
async def list_transactions(
    user_id: Annotated[str, Query(description="ID of the user")],
    tx_type: Annotated[
        list[TransactionType] | None, Query(description="Transaction types")
    ] = None,
    credit_debit: Annotated[
        CreditDebit | None, Query(description="Credit or debit")
    ] = None,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of transactions to return", ge=1, le=100)
    ] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreditTransactionsResponse:
    """List transactions with optional filtering by transaction type and credit/debit.

    You can use the `credit_debit` field to filter for debits or credits.
    Alternatively, you can use `tx_type` to directly specify the transaction types you need.
    For example, selecting `receive_fee_dev` and `reward` will query only those two types
    of rewards; this way, topup will not be included.

    Args:
        user_id: ID of the user
        tx_type: Optional filter for transaction type
        credit_debit: Optional filter for credit or debit
        cursor: Cursor for pagination
        limit: Maximum number of transactions to return
        db: Database session

    Returns:
        Response with list of transactions and pagination information
    """
    # First get the account ID for the user
    account_query = select(CreditAccountTable.id).where(
        CreditAccountTable.owner_type == OwnerType.USER,
        CreditAccountTable.owner_id == user_id,
    )
    account_result = await db.execute(account_query)
    account_id = account_result.scalar_one_or_none()

    if not account_id:
        # Return empty response if account doesn't exist
        return CreditTransactionsResponse(
            data=[],
            has_more=False,
            next_cursor=None,
        )

    # Build query for transactions
    query = select(CreditTransactionTable).where(
        CreditTransactionTable.account_id == account_id
    )

    # Apply optional filters
    if tx_type:
        query = query.where(CreditTransactionTable.tx_type.in_(tx_type))

    if credit_debit:
        query = query.where(CreditTransactionTable.credit_debit == credit_debit)

    # Apply pagination
    if cursor:
        # Use ID directly as cursor since IDs are time-ordered
        query = query.where(CreditTransactionTable.id < cursor)

    # Order by created_at desc, id desc for consistent pagination
    query = query.order_by(CreditTransactionTable.id.desc()).limit(
        limit + 1
    )  # Fetch one extra to determine if there are more

    result = await db.execute(query)
    transactions = result.scalars().all()

    # Check if there are more results
    has_more = len(transactions) > limit
    if has_more:
        transactions = transactions[:-1]  # Remove the extra item

    # Generate next cursor
    next_cursor = None
    if has_more and transactions:
        last_tx = transactions[-1]
        next_cursor = last_tx.id

    # Convert SQLAlchemy models to Pydantic models
    tx_models = [CreditTransaction.model_validate(tx) for tx in transactions]

    # Get all unique event IDs
    event_ids = {tx.event_id for tx in tx_models}

    # Fetch all related events in a single query
    events_map = {}
    if event_ids:
        events_query = select(CreditEventTable).where(
            CreditEventTable.id.in_(event_ids)
        )
        events_result = await db.execute(events_query)
        events = events_result.scalars().all()

        # Create a map of event_id to CreditEvent
        events_map = {event.id: CreditEvent.model_validate(event) for event in events}

    # Create response objects with associated events
    tx_resp_models = []
    for tx in tx_models:
        tx_resp = CreditTransactionResp(
            **tx.model_dump(), event=events_map.get(tx.event_id)
        )
        tx_resp_models.append(tx_resp)

    return CreditTransactionsResponse(
        data=tx_resp_models,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@credit_router.get(
    "/event/users/{user_id}/income",
    response_model=CreditEventsResponse,
    operation_id="list_user_income_events",
    summary="List User Income",
)
async def list_user_income_events(
    user_id: str,
    event_type: Annotated[EventType | None, Query(description="Event type")] = None,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreditEventsResponse:
    """List all income events for a user account.

    Args:
        user_id: ID of the user
        event_type: Event type
        cursor: Cursor for pagination
        limit: Maximum number of events to return
        db: Database session

    Returns:
        Response with list of income events and pagination information
    """
    events, next_cursor, has_more = await list_credit_events_by_user(
        session=db,
        user_id=user_id,
        direction=Direction.INCOME,
        cursor=cursor,
        limit=limit,
        event_type=event_type,
    )

    return CreditEventsResponse(
        data=events,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@credit_router.get(
    "/event/agents/{agent_id}/income",
    response_model=CreditEventsResponse,
    operation_id="list_agent_income_events",
    summary="List Agent Income",
)
async def list_agent_income_events(
    agent_id: str,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreditEventsResponse:
    """List all income events for an agent account.

    Args:
        agent_id: ID of the agent
        cursor: Cursor for pagination
        limit: Maximum number of events to return
        db: Database session

    Returns:
        Response with list of income events and pagination information
    """
    events, next_cursor, has_more = await list_fee_events_by_agent(
        session=db,
        agent_id=agent_id,
        cursor=cursor,
        limit=limit,
    )

    return CreditEventsResponse(
        data=events,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@credit_router.get(
    "/event",
    response_model=CreditEvent,
    operation_id="fetch_credit_event_by_upstream_tx_id",
    summary="Credit Event by Upstream ID",
)
async def fetch_credit_event(
    upstream_tx_id: Annotated[str, Query(description="Upstream transaction ID")],
    db: AsyncSession = Depends(get_db),
) -> CreditEvent:
    """Fetch a credit event by its upstream transaction ID.

    Args:
        upstream_tx_id: ID of the upstream transaction
        db: Database session

    Returns:
        Credit event

    Raises:
        404: If the credit event is not found
    """
    return await fetch_credit_event_by_upstream_tx_id(db, upstream_tx_id)


@credit_router.get(
    "/events/{event_id}",
    response_model=CreditEvent,
    operation_id="fetch_credit_event_by_id",
    summary="Credit Event by ID",
    responses={
        200: {"description": "Credit event found and returned successfully"},
        403: {
            "description": "Forbidden: Credit event does not belong to the specified user"
        },
        404: {
            "description": "Not Found: Credit event with the specified ID does not exist"
        },
    },
)
async def fetch_credit_event_by_id_endpoint(
    event_id: Annotated[str, Path(description="Credit event ID")],
    user_id: Annotated[
        str | None, Query(description="Optional user ID for authorization check")
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> CreditEvent:
    """Fetch a credit event by its ID.

    Args:
        event_id: ID of the credit event
        user_id: Optional user ID for authorization check
        db: Database session

    Returns:
        Credit event

    Raises:
        404: If the credit event is not found
        403: If the event's account does not belong to the provided user_id
    """
    event = await fetch_credit_event_by_id(db, event_id)

    # If user_id is provided, check if the event's account belongs to this user
    if user_id:
        # Query to find the account by ID
        stmt = select(CreditAccountTable).where(
            CreditAccountTable.id == event.account_id,
            CreditAccountTable.owner_type == "user",
            CreditAccountTable.owner_id == user_id,
        )

        # Execute query
        account = await db.scalar(stmt)

        # If no matching account found, the event doesn't belong to this user
        if not account:
            raise IntentKitAPIError(
                403,
                "Forbidden",
                f"Credit event with ID '{event_id}' does not belong to user '{user_id}'",
            )

    return event


@credit_router.get(
    "/events",
    operation_id="list_credit_events",
    summary="List Credit Events",
    response_model=CreditEventsResponse,
)
async def list_all_credit_events(
    direction: Annotated[
        Direction | None,
        Query(description="Direction of credit events (income or expense)"),
    ] = Direction.EXPENSE,
    event_type: Annotated[EventType | None, Query(description="Event type")] = None,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    start_at: Annotated[
        datetime | None,
        Query(description="Start datetime for filtering events, inclusive"),
    ] = None,
    end_at: Annotated[
        datetime | None,
        Query(description="End datetime for filtering events, exclusive"),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> CreditEventsResponse:
    """
    List all credit events for admin monitoring with cursor pagination.

    This endpoint is designed for admin use to monitor all credit events in the system.
    Only the first request does not need a cursor, then always use the last cursor for subsequent requests.
    Even when there are no records, it will still return a cursor that can be used for the next request.
    You can poll this endpoint using the cursor every second - when new records are created, you will get them.

    """
    events, next_cursor, has_more = await list_credit_events(
        session=db,
        direction=direction,
        cursor=cursor,
        limit=limit,
        event_type=event_type,
        start_at=start_at,
        end_at=end_at,
    )

    return CreditEventsResponse(
        data=events,
        next_cursor=next_cursor if next_cursor else cursor,
        has_more=has_more,
    )
