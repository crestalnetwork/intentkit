"""Team management endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import BaseModel, Field, TypeAdapter

from intentkit.core.team.membership import (
    check_permission,
    create_invite,
    create_team,
    get_members,
    join_team,
    remove_member,
    update_team,
)
from intentkit.models.team import TeamMember, TeamRole
from intentkit.models.user import User, UserUpdate
from intentkit.utils.error import IntentKitAPIError

from app.team.auth import get_current_user, verify_team_admin, verify_team_member
from app.team.user import invalidate_user_cache

_team_member_list_adapter = TypeAdapter(list[TeamMember])

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


class JoinTeamRequest(BaseModel):
    code: str = Field(..., description="Invite code")


class UpdateTeamRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    avatar: str | None = None


@team_management_router.post("/teams/join")
async def join_team_endpoint(
    body: JoinTeamRequest = Body(...),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Join a team using an invite code."""
    try:
        team = await join_team(body.code, user_id)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400,
            key="JoinTeamFailed",
            message=str(e),
        )

    # Auto-switch to the joined team
    await UserUpdate.model_validate({"current_team_id": team.id}).patch(user_id)
    await invalidate_user_cache(user_id)

    return Response(content=team.model_dump_json(), media_type="application/json")


@team_management_router.get("/teams/{team_id}/members")
async def list_members_endpoint(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """List all members of a team. Requires team membership."""
    _, team_id = auth
    members = await get_members(team_id)
    return Response(
        content=_team_member_list_adapter.dump_json(members),
        media_type="application/json",
    )


@team_management_router.patch("/teams/{team_id}")
async def update_team_endpoint(
    body: UpdateTeamRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> Response:
    """Update team info. Requires admin or owner role."""
    _, team_id = auth
    try:
        team = await update_team(team_id, name=body.name, avatar=body.avatar)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400,
            key="TeamUpdateFailed",
            message=str(e),
        )
    return Response(content=team.model_dump_json(), media_type="application/json")


@team_management_router.delete("/teams/{team_id}/members/{member_id}")
async def remove_member_endpoint(
    member_id: str = Path(..., description="User ID of the member to remove"),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> Response:
    """Remove a member from the team. Requires admin or owner role.

    Admins can only remove members; owners can remove anyone (except the last owner).
    """
    caller_id, team_id = auth

    # Admins can only remove members; owners can remove anyone except the last owner
    caller_is_owner = await check_permission(team_id, caller_id, TeamRole.OWNER)
    if not caller_is_owner:
        target_is_admin = await check_permission(team_id, member_id, TeamRole.ADMIN)
        if target_is_admin:
            raise IntentKitAPIError(
                status_code=403,
                key="InsufficientRole",
                message="Only owners can remove admins or owners",
            )

    try:
        await remove_member(team_id, member_id)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400,
            key="RemoveMemberFailed",
            message=str(e),
        )

    # Clear removed user's current_team_id if it pointed to this team
    removed_user = await User.get(member_id)
    if removed_user and removed_user.current_team_id == team_id:
        await UserUpdate.model_validate({"current_team_id": None}).patch(member_id)
        await invalidate_user_cache(member_id)

    return Response(content='{"ok":true}', media_type="application/json")
