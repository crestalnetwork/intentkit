import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.config import config
from app.core.credit import (
    fetch_credit_event_by_id,
    fetch_credit_event_by_upstream_tx_id,
    list_credit_events,
    list_credit_events_by_user,
    list_fee_events_by_agent,
    recharge,
    reward,
    update_daily_quota,
)
from models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditEvent,
    CreditEventTable,
    Direction,
    EventType,
    OwnerType,
)
from models.db import get_db
from utils.middleware import create_jwt_middleware

logger = logging.getLogger(__name__)
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)

credit_router = APIRouter(prefix="/credit", tags=["Credit"])
credit_router_readonly = APIRouter(prefix="/credit", tags=["Credit"])


# ===== Models =====
class CreditEventsResponse(BaseModel):
    """Response model for credit events with pagination."""

    data: List[CreditEvent] = Field(description="List of credit events")
    has_more: bool = Field(description="Indicates if there are more items")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")


# ===== Input models =====
class RechargeRequest(BaseModel):
    """Request model for recharging a user account."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    user_id: Annotated[str, Field(description="ID of the user to recharge")]
    amount: Annotated[Decimal, Field(gt=Decimal("0"), description="Amount to recharge")]
    note: Annotated[
        Optional[str], Field(None, description="Optional note for the recharge")
    ]


class RewardRequest(BaseModel):
    """Request model for rewarding a user account."""

    upstream_tx_id: Annotated[
        str, Field(str, description="Upstream transaction ID, idempotence Check")
    ]
    user_id: Annotated[str, Field(description="ID of the user to reward")]
    amount: Annotated[Decimal, Field(gt=Decimal("0"), description="Amount to reward")]
    note: Annotated[
        Optional[str], Field(None, description="Optional note for the reward")
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
        Optional[Decimal],
        Field(
            None, gt=Decimal("0"), description="New daily quota value for the account"
        ),
    ]
    refill_amount: Annotated[
        Optional[Decimal],
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


# ===== Agent Statistics =====
class AgentStatisticsResponse(BaseModel):
    """Response model for agent statistics."""

    agent_id: str = Field(description="ID of the agent")
    account_id: str = Field(description="ID of the agent's credit account")
    balance: Decimal = Field(description="Total balance of the agent's account")
    total_income: Decimal = Field(description="Total income from all credit events")
    net_income: Decimal = Field(description="Net income from all credit events")


# ===== API Endpoints =====
@credit_router.get(
    "/accounts/{owner_type}/{owner_id}",
    response_model=CreditAccount,
    operation_id="get_account",
    summary="Get Account",
    dependencies=[Depends(verify_jwt)],
)
async def get_account(owner_type: OwnerType, owner_id: str) -> CreditAccount:
    """Get a credit account by owner type and ID. It will create a new account if it does not exist.

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
    dependencies=[Depends(verify_jwt)],
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
    dependencies=[Depends(verify_jwt)],
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
        db, request.user_id, request.amount, request.upstream_tx_id, request.note
    )


# @credit_router.post(
#     "/adjust",
#     response_model=CreditAccount,
#     status_code=status.HTTP_201_CREATED,
#     operation_id="adjust_account",
#     summary="Adjust",
#     dependencies=[Depends(verify_jwt)],
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
    dependencies=[Depends(verify_jwt)],
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
    response_model=AgentStatisticsResponse,
    operation_id="get_agent_statistics",
    summary="Get Agent Statistics",
    dependencies=[Depends(verify_jwt)],
)
async def get_agent_statistics(
    agent_id: Annotated[str, Path(description="ID of the agent")],
    db: AsyncSession = Depends(get_db),
) -> AgentStatisticsResponse:
    """Get statistics for an agent account.

    Args:
        agent_id: ID of the agent
        db: Database session

    Returns:
        Agent statistics including balance, total income, and net income

    Raises:
        404: If the agent account is not found
    """
    # Get the agent account
    agent_account = await CreditAccount.get_or_create_in_session(
        db, OwnerType.AGENT, agent_id
    )

    # Calculate the total balance
    balance = (
        agent_account.free_credits
        + agent_account.reward_credits
        + agent_account.credits
    )

    # Calculate total income (sum of total_amount) and net income (sum of fee_agent_amount) at SQL level
    # Query to get the sum of total_amount and fee_agent_amount
    stmt = select(
        func.sum(CreditEventTable.total_amount).label("total_income"),
        func.sum(CreditEventTable.fee_agent_amount).label("net_income"),
    ).where(CreditEventTable.agent_id == agent_id)
    result = await db.execute(stmt)
    row = result.first()

    # Extract the sums, defaulting to 0 if None
    total_income = row.total_income if row.total_income is not None else Decimal("0")
    net_income = row.net_income if row.net_income is not None else Decimal("0")

    return AgentStatisticsResponse(
        agent_id=agent_id,
        account_id=agent_account.id,
        balance=balance,
        total_income=total_income,
        net_income=net_income,
    )


@credit_router_readonly.get(
    "/users/{user_id}/events",
    response_model=CreditEventsResponse,
    operation_id="list_user_events",
    summary="List User Events",
    dependencies=[Depends(verify_jwt)],
)
async def list_user_events(
    user_id: str,
    event_type: Annotated[Optional[EventType], Query(description="Event type")] = None,
    cursor: Annotated[Optional[str], Query(description="Cursor for pagination")] = None,
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


@credit_router_readonly.get(
    "/event/users/{user_id}/expense",
    response_model=CreditEventsResponse,
    operation_id="list_user_expense_events",
    summary="List User Expense",
    dependencies=[Depends(verify_jwt)],
)
async def list_user_expense_events(
    user_id: str,
    cursor: Annotated[Optional[str], Query(description="Cursor for pagination")] = None,
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


@credit_router_readonly.get(
    "/event/users/{user_id}/income",
    response_model=CreditEventsResponse,
    operation_id="list_user_income_events",
    summary="List User Income",
    dependencies=[Depends(verify_jwt)],
)
async def list_user_income_events(
    user_id: str,
    event_type: Annotated[Optional[EventType], Query(description="Event type")] = None,
    cursor: Annotated[Optional[str], Query(description="Cursor for pagination")] = None,
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


@credit_router_readonly.get(
    "/event/agents/{agent_id}/income",
    response_model=CreditEventsResponse,
    operation_id="list_agent_income_events",
    summary="List Agent Income",
    dependencies=[Depends(verify_jwt)],
)
async def list_agent_income_events(
    agent_id: str,
    cursor: Annotated[Optional[str], Query(description="Cursor for pagination")] = None,
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


@credit_router_readonly.get(
    "/event",
    response_model=CreditEvent,
    operation_id="fetch_credit_event_by_upstream_tx_id",
    summary="Credit Event by Upstream ID",
    dependencies=[Depends(verify_jwt)],
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


@credit_router_readonly.get(
    "/events/{event_id}",
    response_model=CreditEvent,
    operation_id="fetch_credit_event_by_id",
    summary="Credit Event by ID",
    dependencies=[Depends(verify_jwt)],
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
        Optional[str], Query(description="Optional user ID for authorization check")
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
            raise HTTPException(
                status_code=403,
                detail=f"Credit event with ID '{event_id}' does not belong to user '{user_id}'",
            )

    return event


@credit_router_readonly.get(
    "/events",
    operation_id="list_credit_events",
    summary="List Credit Events",
    response_model=CreditEventsResponse,
)
async def list_all_credit_events(
    direction: Annotated[
        Optional[Direction],
        Query(description="Direction of credit events (income or expense)"),
    ] = Direction.EXPENSE,
    event_type: Annotated[Optional[EventType], Query(description="Event type")] = None,
    cursor: Annotated[Optional[str], Query(description="Cursor for pagination")] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", ge=1, le=100)
    ] = 20,
    start_at: Annotated[
        Optional[datetime],
        Query(description="Start datetime for filtering events, inclusive"),
    ] = None,
    end_at: Annotated[
        Optional[datetime],
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
