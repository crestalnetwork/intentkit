"""Team content feed and subscription endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.core.team.feed import query_activity_feed, query_post_feed
from intentkit.core.team.subscription import (
    get_subscriptions,
    subscribe_agent,
    unsubscribe_agent,
)
from intentkit.models.agent_activity import AgentActivity, AgentActivityTable
from intentkit.models.agent_post import AgentPost, AgentPostBrief, AgentPostTable
from intentkit.models.team_feed import TeamFeedPage, TeamSubscription
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.pdf import post_pdf_response

from app.team.agent import get_accessible_agent
from app.team.auth import verify_team_member

team_content_router = APIRouter(tags=["Content"])


@team_content_router.get(
    "/teams/{team_id}/feed/activities",
    operation_id="team_activity_feed",
    response_model=TeamFeedPage[AgentActivity],
)
async def get_activity_feed(
    auth: tuple[str, str] = Depends(verify_team_member),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> TeamFeedPage[AgentActivity]:
    _, team_id = auth
    items, next_cursor = await query_activity_feed(team_id, limit, cursor)
    return TeamFeedPage(items=items, next_cursor=next_cursor)


@team_content_router.get(
    "/teams/{team_id}/feed/posts",
    operation_id="team_post_feed",
    response_model=TeamFeedPage[AgentPostBrief],
)
async def get_post_feed(
    auth: tuple[str, str] = Depends(verify_team_member),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> TeamFeedPage[AgentPostBrief]:
    _, team_id = auth
    items, next_cursor = await query_post_feed(team_id, limit, cursor)
    return TeamFeedPage(items=items, next_cursor=next_cursor)


@team_content_router.get(
    "/teams/{team_id}/subscriptions",
    operation_id="team_list_subscriptions",
    response_model=list[TeamSubscription],
)
async def list_subscriptions(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[TeamSubscription]:
    _, team_id = auth
    return await get_subscriptions(team_id)


@team_content_router.post(
    "/teams/{team_id}/subscriptions/{agent_id}",
    operation_id="team_subscribe_agent",
    response_model=TeamSubscription,
    status_code=201,
)
async def subscribe(
    agent_id: str,
    auth: tuple[str, str] = Depends(verify_team_member),
) -> TeamSubscription:
    _, team_id = auth
    return await subscribe_agent(team_id, agent_id)


@team_content_router.delete(
    "/teams/{team_id}/subscriptions/{agent_id}",
    operation_id="team_unsubscribe_agent",
    status_code=204,
)
async def unsubscribe(
    agent_id: str,
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    _, team_id = auth
    await unsubscribe_agent(team_id, agent_id)
    return Response(status_code=204)


@team_content_router.get(
    "/teams/{team_id}/agents/{agent_id}/activities",
    operation_id="team_agent_activities",
    response_model=list[AgentActivity],
)
async def get_agent_activities(
    agent_id: str = Path(...),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AgentActivity]:
    """Get all activities for a team's agent."""
    _, team_id = auth
    await get_accessible_agent(agent_id, team_id)

    async with get_session() as db:
        stmt = (
            select(AgentActivityTable)
            .where(AgentActivityTable.agent_id == agent_id)
            .order_by(AgentActivityTable.created_at.desc())
        )
        activities = (await db.scalars(stmt)).all()
        return [AgentActivity.model_validate(a) for a in activities]


@team_content_router.get(
    "/teams/{team_id}/agents/{agent_id}/posts",
    operation_id="team_agent_posts",
    response_model=list[AgentPostBrief],
)
async def get_agent_posts(
    agent_id: str = Path(...),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AgentPostBrief]:
    """Get all posts for a team's agent with truncated content."""
    _, team_id = auth
    await get_accessible_agent(agent_id, team_id)

    async with get_session() as db:
        stmt = (
            select(AgentPostTable)
            .where(AgentPostTable.agent_id == agent_id)
            .order_by(AgentPostTable.created_at.desc())
        )
        posts = (await db.scalars(stmt)).all()
        return [AgentPostBrief.from_table(p) for p in posts]


@team_content_router.get(
    "/teams/{team_id}/posts/{post_id}",
    operation_id="team_get_post",
    response_model=AgentPost,
)
async def get_post(
    post_id: str = Path(...),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AgentPost:
    """Get a single post by ID with full content."""
    _, team_id = auth

    async with get_session() as db:
        stmt = select(AgentPostTable).where(AgentPostTable.id == post_id)
        post = (await db.scalars(stmt)).first()
        if not post:
            raise IntentKitAPIError(
                status_code=404, key="NotFound", message="Post not found"
            )

    await get_accessible_agent(post.agent_id, team_id)
    return AgentPost.model_validate(post)


@team_content_router.get(
    "/teams/{team_id}/posts/{post_id}/pdf",
    operation_id="team_get_post_pdf",
)
async def get_post_pdf(
    post_id: str = Path(...),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Download a post as a styled PDF file."""
    _, team_id = auth

    async with get_session() as db:
        stmt = select(AgentPostTable).where(AgentPostTable.id == post_id)
        post = (await db.scalars(stmt)).first()
        if not post:
            raise IntentKitAPIError(
                status_code=404, key="NotFound", message="Post not found"
            )

    await get_accessible_agent(post.agent_id, team_id)
    return await post_pdf_response(post, cdn_base=config.aws_s3_cdn_url)
