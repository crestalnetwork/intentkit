"""Shared public API router for both local and team APIs."""

from fastapi import APIRouter, Path, Query
from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.core.agent_post import get_agent_post
from intentkit.core.team.feed import query_activity_feed, query_post_feed
from intentkit.models.agent import Agent, AgentResponse
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent_activity import AgentActivity
from intentkit.models.agent_post import AgentPost, AgentPostBrief
from intentkit.models.team_feed import TeamFeedPage
from intentkit.utils.error import IntentKitAPIError

PUBLIC_TEAM_ID = "public"


def create_public_router() -> APIRouter:
    """Create a public API router with endpoints for public agents/feed/posts."""
    router = APIRouter(prefix="/public", tags=["Public"])

    @router.get("/agents", operation_id="public_list_agents")
    async def list_public_agents() -> list[AgentResponse]:
        """List all public agents (visibility >= PUBLIC)."""
        async with get_session() as session:
            result = await session.execute(
                select(AgentTable)
                .where(AgentTable.visibility >= AgentVisibility.PUBLIC)
                .where(AgentTable.archived_at.is_(None))
                .order_by(AgentTable.created_at.desc())
            )
            agents = result.scalars().all()
            responses = []
            for agent_row in agents:
                agent = Agent.model_validate(agent_row)
                resp = await AgentResponse.from_agent(agent)
                responses.append(resp)
            return responses

    @router.get("/timeline", operation_id="public_timeline")
    async def public_timeline(
        limit: int = Query(20, ge=1, le=100),
        cursor: str | None = Query(None),
    ) -> TeamFeedPage[AgentActivity]:
        """Get public activity timeline."""
        items, next_cursor = await query_activity_feed(PUBLIC_TEAM_ID, limit, cursor)
        return TeamFeedPage(items=items, next_cursor=next_cursor)

    @router.get("/posts", operation_id="public_posts")
    async def public_posts(
        limit: int = Query(20, ge=1, le=100),
        cursor: str | None = Query(None),
    ) -> TeamFeedPage[AgentPostBrief]:
        """Get public posts feed."""
        items, next_cursor = await query_post_feed(PUBLIC_TEAM_ID, limit, cursor)
        return TeamFeedPage(items=items, next_cursor=next_cursor)

    @router.get("/posts/{post_id}", operation_id="public_get_post")
    async def public_get_post(post_id: str = Path(...)) -> AgentPost:
        """Get a single public post by ID.

        Only returns posts that belong to public agents (visibility >= PUBLIC).
        """
        post = await get_agent_post(post_id)
        if not post:
            raise IntentKitAPIError(404, "NotFound", "Post not found")
        # Verify the post belongs to a public agent
        async with get_session() as session:
            agent_row = await session.get(AgentTable, post.agent_id)
            if (
                not agent_row
                or agent_row.visibility is None
                or agent_row.visibility < AgentVisibility.PUBLIC
            ):
                raise IntentKitAPIError(404, "NotFound", "Post not found")
        return post

    return router
