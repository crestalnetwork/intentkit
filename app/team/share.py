"""Team API share-link endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from intentkit.config.config import config
from intentkit.core.agent_post import get_agent_post
from intentkit.core.share_link import create_share_link
from intentkit.core.team.membership import check_permission
from intentkit.models.chat import Chat
from intentkit.models.share_link import ShareLinkTargetType
from intentkit.models.team import TeamRole
from intentkit.utils.error import IntentKitAPIError

from app.team.agent import get_accessible_agent
from app.team.auth import verify_team_member

team_share_router = APIRouter(tags=["Share"])

logger = logging.getLogger(__name__)


class ShareLinkRequest(BaseModel):
    """Request body for creating a share link."""

    target_type: ShareLinkTargetType
    target_id: str


class ShareLinkResponse(BaseModel):
    """Response returned after creating a share link."""

    id: str
    url: str
    target_type: ShareLinkTargetType
    expires_at: datetime


def _build_share_url(share_link_id: str) -> str:
    return f"{config.app_base_url.rstrip('/')}/share/{share_link_id}"


@team_share_router.post(
    "/teams/{team_id}/share-links",
    operation_id="team_create_share_link",
    status_code=201,
    response_model=ShareLinkResponse,
    summary="Create share link (Team)",
)
async def create_team_share_link(
    payload: ShareLinkRequest,
    auth: tuple[str, str] = Depends(verify_team_member),
) -> ShareLinkResponse:
    """Create a time-limited public share link for a post or chat.

    The caller must be a team member. The target must belong to an agent the team
    can access; for chats, the chat owner must also be a team member.
    """
    user_id, team_id = auth

    if payload.target_type == ShareLinkTargetType.POST:
        post = await get_agent_post(payload.target_id)
        if post is None:
            raise IntentKitAPIError(
                status_code=404, key="NotFound", message="Post not found"
            )
        await get_accessible_agent(post.agent_id, team_id)
        agent_id = post.agent_id
    else:
        chat = await Chat.get(payload.target_id)
        if chat is None:
            raise IntentKitAPIError(
                status_code=404, key="NotFound", message="Chat not found"
            )
        await get_accessible_agent(chat.agent_id, team_id)
        if not await check_permission(team_id, chat.user_id, TeamRole.MEMBER):
            raise IntentKitAPIError(
                status_code=404, key="NotFound", message="Chat not found"
            )
        agent_id = chat.agent_id

    link = await create_share_link(
        payload.target_type,
        payload.target_id,
        agent_id,
        user_id=user_id,
        team_id=team_id,
    )
    return ShareLinkResponse(
        id=link.id,
        url=_build_share_url(link.id),
        target_type=link.target_type,
        expires_at=link.expires_at,
    )
