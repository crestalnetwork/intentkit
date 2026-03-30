"""Content APIs for local development - Activities and Posts."""

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.config.db import get_db
from intentkit.core.team.subscription import (
    get_subscriptions,
    subscribe_agent,
    unsubscribe_agent,
)
from intentkit.models.agent_activity import AgentActivity, AgentActivityTable
from intentkit.models.agent_post import AgentPost, AgentPostBrief, AgentPostTable
from intentkit.models.team_feed import TeamSubscription
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.pdf import post_pdf_response

content_router = APIRouter()


@content_router.get(
    "/activities",
    tags=["Content"],
    operation_id="get_all_activities",
    summary="Get All Activities",
)
async def get_all_activities(
    db: AsyncSession = Depends(get_db),
) -> list[AgentActivity]:
    """Get all activities across all agents.

    **Returns:**
    * `list[AgentActivity]` - List of all activities sorted by created_at descending
    """
    stmt = select(AgentActivityTable).order_by(AgentActivityTable.created_at.desc())
    activities = (await db.scalars(stmt)).all()
    return [AgentActivity.model_validate(a) for a in activities]


@content_router.get(
    "/agents/{agent_id}/activities",
    tags=["Content"],
    operation_id="get_agent_activities",
    summary="Get Agent Activities",
)
async def get_agent_activities(
    agent_id: str = Path(..., description="ID of the agent"),
    db: AsyncSession = Depends(get_db),
) -> list[AgentActivity]:
    """Get all activities for a specific agent.

    **Path Parameters:**
    * `agent_id` - ID of the agent

    **Returns:**
    * `list[AgentActivity]` - List of activities for the agent sorted by created_at descending
    """
    stmt = (
        select(AgentActivityTable)
        .where(AgentActivityTable.agent_id == agent_id)
        .order_by(AgentActivityTable.created_at.desc())
    )
    activities = (await db.scalars(stmt)).all()
    return [AgentActivity.model_validate(a) for a in activities]


@content_router.get(
    "/posts",
    tags=["Content"],
    operation_id="get_all_posts",
    summary="Get All Posts (Brief)",
)
async def get_all_posts(
    db: AsyncSession = Depends(get_db),
) -> list[AgentPostBrief]:
    """Get all posts across all agents with truncated content.

    **Returns:**
    * `list[AgentPostBrief]` - List of all posts with content truncated to 500 characters
    """
    stmt = select(AgentPostTable).order_by(AgentPostTable.created_at.desc())
    posts = (await db.scalars(stmt)).all()
    return [AgentPostBrief.from_table(p) for p in posts]


@content_router.get(
    "/agents/{agent_id}/posts",
    tags=["Content"],
    operation_id="get_agent_posts",
    summary="Get Agent Posts (Brief)",
)
async def get_agent_posts(
    agent_id: str = Path(..., description="ID of the agent"),
    db: AsyncSession = Depends(get_db),
) -> list[AgentPostBrief]:
    """Get all posts for a specific agent with truncated content.

    **Path Parameters:**
    * `agent_id` - ID of the agent

    **Returns:**
    * `list[AgentPostBrief]` - List of posts for the agent with content truncated to 500 characters
    """
    stmt = (
        select(AgentPostTable)
        .where(AgentPostTable.agent_id == agent_id)
        .order_by(AgentPostTable.created_at.desc())
    )
    posts = (await db.scalars(stmt)).all()
    return [AgentPostBrief.from_table(p) for p in posts]


@content_router.get(
    "/posts/{post_id}",
    tags=["Content"],
    operation_id="get_post",
    summary="Get Post",
)
async def get_post(
    post_id: str = Path(..., description="ID of the post"),
    db: AsyncSession = Depends(get_db),
) -> AgentPost:
    """Get a single post by ID with full content.

    **Path Parameters:**
    * `post_id` - ID of the post

    **Returns:**
    * `AgentPost` - Full post content

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Post not found
    """
    stmt = select(AgentPostTable).where(AgentPostTable.id == post_id)
    post = (await db.scalars(stmt)).first()
    if not post:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Post not found"
        )
    return AgentPost.model_validate(post)


@content_router.get(
    "/agents/{agent_id}/posts/slug/{slug}",
    tags=["Content"],
    operation_id="get_post_by_slug",
    summary="Get Post by Slug",
)
async def get_post_by_slug(
    agent_id: str = Path(..., description="ID of the agent"),
    slug: str = Path(..., description="Slug of the post"),
    db: AsyncSession = Depends(get_db),
) -> AgentPost:
    """Get a single post by Agent ID and Slug with full content.

    **Path Parameters:**
    * `agent_id` - ID of the agent
    * `slug` - Slug of the post

    **Returns:**
    * `AgentPost` - Full post content

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Post not found
    """
    stmt = select(AgentPostTable).where(
        AgentPostTable.agent_id == agent_id,
        AgentPostTable.slug == slug,
    )
    post = (await db.scalars(stmt)).first()
    if not post:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Post not found"
        )
    return AgentPost.model_validate(post)


@content_router.get(
    "/posts/{post_id}/pdf",
    tags=["Content"],
    operation_id="get_post_pdf",
    summary="Download Post as PDF",
)
async def get_post_pdf(
    post_id: str = Path(..., description="ID of the post"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a post as a styled PDF file."""
    stmt = select(AgentPostTable).where(AgentPostTable.id == post_id)
    post = (await db.scalars(stmt)).first()
    if not post:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Post not found"
        )
    return await post_pdf_response(post, cdn_base=config.aws_s3_cdn_url)


@content_router.get(
    "/agents/{agent_id}/posts/slug/{slug}/pdf",
    tags=["Content"],
    operation_id="get_post_pdf_by_slug",
    summary="Download Post as PDF by Slug",
)
async def get_post_pdf_by_slug(
    agent_id: str = Path(..., description="ID of the agent"),
    slug: str = Path(..., description="Slug of the post"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a post as a styled PDF file by agent ID and slug."""
    stmt = select(AgentPostTable).where(
        AgentPostTable.agent_id == agent_id,
        AgentPostTable.slug == slug,
    )
    post = (await db.scalars(stmt)).first()
    if not post:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Post not found"
        )
    return await post_pdf_response(
        post, filename=f"{slug}.pdf", cdn_base=config.aws_s3_cdn_url
    )


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------

LOCAL_TEAM_ID = "system"


@content_router.get(
    "/subscriptions",
    tags=["Content"],
    operation_id="list_subscriptions",
)
async def list_subscriptions_endpoint() -> list[TeamSubscription]:
    """List all subscriptions for the system team."""
    return await get_subscriptions(LOCAL_TEAM_ID)


@content_router.post(
    "/subscriptions/{agent_id}",
    tags=["Content"],
    operation_id="subscribe_agent",
    status_code=201,
)
async def subscribe_endpoint(agent_id: str = Path(...)) -> TeamSubscription:
    """Subscribe the system team to an agent."""
    return await subscribe_agent(LOCAL_TEAM_ID, agent_id)


@content_router.delete(
    "/subscriptions/{agent_id}",
    tags=["Content"],
    operation_id="unsubscribe_agent",
    status_code=204,
)
async def unsubscribe_endpoint(agent_id: str = Path(...)) -> Response:
    """Unsubscribe the system team from an agent."""
    await unsubscribe_agent(LOCAL_TEAM_ID, agent_id)
    return Response(status_code=204)
