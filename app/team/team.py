"""Team management endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Response
from pydantic import BaseModel, Field

from intentkit.core.team.membership import create_invite, create_team
from intentkit.models.team import TeamRole
from intentkit.models.user import UserUpdate
from intentkit.utils.error import IntentKitAPIError

from app.team.auth import get_current_user, verify_team_admin
from app.team.user import invalidate_user_cache

team_management_router = APIRouter()

logger = logging.getLogger(__name__)


class CreateTeamRequest(BaseModel):
    id: str = Field(
        ..., min_length=2, max_length=60, pattern=r"^[a-z]([a-z0-9-]*[a-z0-9])?$"
    )
    name: str = Field(..., min_length=1, max_length=100)


class CreateInviteRequest(BaseModel):
    role: TeamRole = TeamRole.MEMBER
    max_uses: int | None = None
    expires_at: datetime | None = None


@team_management_router.post("/teams", status_code=201)
async def create_team_endpoint(
    body: CreateTeamRequest = Body(...),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Create a new team. The creator becomes the owner."""
    try:
        team = await create_team(body.id, body.name, user_id)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400,
            key="TeamCreateFailed",
            message=str(e),
        )

    await UserUpdate.model_validate({"current_team_id": team.id}).patch(user_id)
    await invalidate_user_cache(user_id)

    return Response(
        content=team.model_dump_json(),
        media_type="application/json",
        status_code=201,
    )


@team_management_router.post("/teams/{team_id}/invite", status_code=201)
async def create_invite_endpoint(
    body: CreateInviteRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> Response:
    """Create a team invite code. Requires admin or owner role."""
    user_id, team_id = auth
    try:
        invite = await create_invite(
            team_id=team_id,
            invited_by=user_id,
            role=body.role,
            max_uses=body.max_uses,
            expires_at=body.expires_at,
        )
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400,
            key="InviteCreateFailed",
            message=str(e),
        )

    return Response(
        content=invite.model_dump_json(),
        media_type="application/json",
        status_code=201,
    )
