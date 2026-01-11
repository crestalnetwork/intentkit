import json
import logging

from sqlalchemy import select

from intentkit.models.agent_post import AgentPost, AgentPostCreate, AgentPostTable
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis

logger = logging.getLogger(__name__)


async def create_agent_post(post_create: AgentPostCreate) -> AgentPost:
    """
    Create a new agent post.

    Args:
        post_create: The data to create the post.

    Returns:
        The created AgentPost.
    """
    async with get_session() as session:
        # Create SQLAlchemy model instance
        db_post = AgentPostTable(
            agent_id=post_create.agent_id,
            agent_name=post_create.agent_name,
            title=post_create.title,
            cover=post_create.cover,
            markdown=post_create.markdown,
            slug=post_create.slug,
            excerpt=post_create.excerpt,
            tags=post_create.tags,
        )
        session.add(db_post)
        await session.commit()
        await session.refresh(db_post)

        return AgentPost.model_validate(db_post)


async def get_agent_post(post_id: str) -> AgentPost | None:
    """
    Get an agent post by ID.

    Args:
        post_id: The ID of the post.

    Returns:
        The AgentPost if found, else None.
    """
    cache_key = f"intentkit:agent_post:{post_id}"
    redis_client = None

    try:
        redis_client = get_redis()
    except Exception as exc:  # pragma: no cover
        logger.debug("Redis unavailable for agent post: %s", exc)

    if redis_client:
        try:
            cached_raw = await redis_client.get(cache_key)
            if cached_raw:
                cached_data = json.loads(cached_raw)
                return AgentPost.model_validate(cached_data)
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to read agent post cache for %s: %s", post_id, exc)

    async with get_session() as session:
        result = await session.execute(
            select(AgentPostTable).where(AgentPostTable.id == post_id)
        )
        db_post = result.scalar_one_or_none()

        if db_post is None:
            return None

        post = AgentPost.model_validate(db_post)

    if redis_client:
        try:
            await redis_client.set(
                cache_key,
                json.dumps(post.model_dump(mode="json")),
                ex=3600,
            )
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to write agent post cache for %s: %s", post_id, exc)

    return post
