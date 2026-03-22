"""Team content feed and subscription endpoints."""

from fastapi import APIRouter, Depends, Query, Response

from intentkit.core.team.feed import query_activity_feed, query_post_feed
from intentkit.core.team.subscription import (
    get_subscriptions,
    subscribe_agent,
    unsubscribe_agent,
)
from intentkit.models.agent_activity import AgentActivity
from intentkit.models.agent_post import AgentPostBrief
from intentkit.models.team_feed import TeamFeedPage, TeamSubscription

from app.team.auth import verify_team_member

team_content_router = APIRouter(tags=["Team Content"])


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
