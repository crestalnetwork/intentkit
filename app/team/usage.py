"""Team usage endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from intentkit.config.db import get_session
from intentkit.core.credit.list_events import list_credit_events_by_team
from intentkit.models.credit import (
    CreditAccount,
    CreditEvent,
    Direction,
    EventType,
    OwnerType,
)
from intentkit.utils.error import IntentKitAPIError

from app.team.auth import verify_team_member

team_usage_router = APIRouter()

logger = logging.getLogger(__name__)


class UsageResponse(BaseModel):
    account: CreditAccount | None
    events: list[CreditEvent]
    next_cursor: str | None
    has_more: bool


@team_usage_router.get("/teams/{team_id}/usage")
async def get_team_usage(
    direction: Direction | None = Query(None, description="Filter by direction"),
    event_type: EventType | None = Query(None, description="Filter by event type"),
    cursor: str | None = Query(None, description="Cursor for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Number of events to return"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Get team credit account and recent usage events."""
    _, team_id = auth

    async with get_session() as session:
        try:
            account = await CreditAccount.get_in_session(
                session, OwnerType.TEAM, team_id
            )
        except IntentKitAPIError:
            account = None

        if account:
            events, next_cursor, has_more = await list_credit_events_by_team(
                session,
                team_id,
                direction=direction,
                cursor=cursor,
                limit=limit,
                event_type=event_type,
            )
        else:
            events, next_cursor, has_more = [], None, False

    resp = UsageResponse(
        account=account,
        events=events,
        next_cursor=next_cursor,
        has_more=has_more,
    )

    return Response(
        content=resp.model_dump_json(),
        media_type="application/json",
    )
