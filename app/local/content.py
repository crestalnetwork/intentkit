"""Content APIs for local development - Activities and Posts."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.agent_activity import AgentActivity, AgentActivityTable
from intentkit.models.agent_post import AgentPost, AgentPostBrief, AgentPostTable
from intentkit.models.db import get_db
from intentkit.utils.error import IntentKitAPIError

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
