"""Core share-link functions: creation (with dedupe), lookup, and view hydration."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.core.agent_post import get_agent_post
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatMessage,
    ChatMessageTable,
)
from intentkit.models.share_link import (
    SharedChatInfo,
    SharedChatView,
    SharedPostView,
    ShareLink,
    ShareLinkTable,
    ShareLinkTargetType,
    ShareLinkView,
)

logger = logging.getLogger(__name__)

SHARE_LINK_DEFAULT_TTL = timedelta(days=3)

# Author types hidden from public share views (internal machinery).
_HIDDEN_AUTHOR_TYPES: set[str] = {
    AuthorType.SKILL.value,
    AuthorType.THINKING.value,
    AuthorType.SYSTEM.value,
}

# Upper bound on messages returned for a shared chat transcript.
_SHARED_CHAT_MESSAGE_LIMIT = 500


def _share_link_cache_key(share_link_id: str) -> str:
    return f"intentkit:share_link:{share_link_id}"


async def create_share_link(
    target_type: ShareLinkTargetType,
    target_id: str,
    agent_id: str,
    *,
    user_id: str | None = None,
    team_id: str | None = None,
    ttl: timedelta = SHARE_LINK_DEFAULT_TTL,
) -> ShareLink:
    """Create a share link, reusing an existing one if it still has at least half of ttl left.

    Dedupe window: if an active link exists for the same (target_type, target_id, agent_id)
    and its remaining lifetime is >= ttl/2, reuse it instead of inserting a new row. This
    keeps DB churn low when the same post is referenced by multiple pushes or activities.

    `user_id` / `team_id` record who initiated the link; they are stored only on the newly
    inserted row. When an existing link is reused, the stored creator is kept as-is.
    """
    now = datetime.now(UTC)
    reuse_threshold = now + ttl / 2
    target_type_value = target_type.value

    async with get_session() as session:
        existing_result = await session.execute(
            select(ShareLinkTable)
            .where(
                ShareLinkTable.target_type == target_type_value,
                ShareLinkTable.target_id == target_id,
                ShareLinkTable.agent_id == agent_id,
                ShareLinkTable.expires_at >= reuse_threshold,
            )
            .order_by(ShareLinkTable.expires_at.desc())
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return ShareLink.model_validate(existing)

        db_link = ShareLinkTable(
            target_type=target_type_value,
            target_id=target_id,
            agent_id=agent_id,
            user_id=user_id,
            team_id=team_id,
            expires_at=now + ttl,
        )
        session.add(db_link)
        await session.commit()
        await session.refresh(db_link)
        return ShareLink.model_validate(db_link)


async def increment_share_link_view_count(share_link_id: str) -> None:
    """Atomically bump `view_count` for a share link. Silent no-op if the row is gone."""
    async with get_session() as session:
        await session.execute(
            update(ShareLinkTable)
            .where(ShareLinkTable.id == share_link_id)
            .values(view_count=ShareLinkTable.view_count + 1)
        )
        await session.commit()


async def get_share_link(share_link_id: str) -> ShareLink | None:
    """Return the share link if present and not expired; otherwise None.

    Uses Redis cache with TTL bounded by the link's remaining lifetime (max 1 hour).
    """
    cache_key = _share_link_cache_key(share_link_id)
    redis_client = get_redis()

    cached_raw = await redis_client.get(cache_key)
    if cached_raw:
        try:
            cached_link = ShareLink.model_validate_json(cached_raw)
        except Exception:
            cached_link = None
        if cached_link and cached_link.expires_at > datetime.now(UTC):
            return cached_link

    async with get_session() as session:
        result = await session.execute(
            select(ShareLinkTable).where(ShareLinkTable.id == share_link_id)
        )
        db_link = result.scalar_one_or_none()

    if db_link is None:
        return None

    link = ShareLink.model_validate(db_link)
    now = datetime.now(UTC)
    if link.expires_at <= now:
        return None

    ttl_seconds = max(1, min(3600, int((link.expires_at - now).total_seconds())))
    await redis_client.set(cache_key, link.model_dump_json(), ex=ttl_seconds)
    return link


async def _load_shared_chat(chat_id: str) -> SharedChatView | None:
    chat = await Chat.get(chat_id)
    if chat is None:
        return None

    async with get_session() as session:
        result = await session.execute(
            select(ChatMessageTable)
            .where(ChatMessageTable.chat_id == chat_id)
            .where(ChatMessageTable.author_type.notin_(_HIDDEN_AUTHOR_TYPES))
            .where(ChatMessageTable.error_type.is_(None))
            .order_by(ChatMessageTable.created_at)
            .limit(_SHARED_CHAT_MESSAGE_LIMIT)
        )
        rows = result.scalars().all()

    messages: list[ChatMessage] = []
    for row in rows:
        msg = ChatMessage.model_validate(row)
        msg.thinking = None
        msg.skill_calls = None
        messages.append(msg)

    info = SharedChatInfo(
        id=chat.id,
        agent_id=chat.agent_id,
        summary=chat.summary,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )
    return SharedChatView(chat=info, messages=messages)


async def get_shared_view(share_link_id: str) -> ShareLinkView | None:
    """Resolve a share link to its hydrated public view. Returns None if expired/missing."""
    link = await get_share_link(share_link_id)
    if link is None:
        return None

    if link.target_type == ShareLinkTargetType.POST:
        post = await get_agent_post(link.target_id)
        if post is None:
            return None
        return ShareLinkView(
            id=link.id,
            target_type=link.target_type,
            expires_at=link.expires_at,
            post=SharedPostView(post=post),
        )

    shared_chat = await _load_shared_chat(link.target_id)
    if shared_chat is None:
        return None
    return ShareLinkView(
        id=link.id,
        target_type=link.target_type,
        expires_at=link.expires_at,
        chat=shared_chat,
    )
