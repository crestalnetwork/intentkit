"""Scoped long-term memories.

Every agent can hold several memories, one row per (agent, scope, scope_key).
All of them work the same way: their content is injected into the system
prompt and updated through the single ``update_memory`` tool. Scopes:

- ``team``: shared by the team using the agent — keyed by the *consuming*
  team's id, so each team talking to a public agent keeps its own memory.
- ``user``: one per user talking to the agent (web/API conversations).
- ``channel``: one per chat thread on a channel platform (Telegram, Slack,
  Lark, ...), keyed by the thread's chat id.
- ``cron``: one per autonomous task, keyed by the task id.

``user``/``channel``/``cron`` are mutually exclusive within a conversation;
``team`` is present whenever the conversation has a consuming team (a
teamless guest has none). Sub-agent runs load no memory at all.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import DateTime, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session

MemoryScopeLiteral = Literal["team", "user", "channel", "cron"]

# Memory rows sit on the prompt-build hot path (read on every model call).
# A short in-process TTL cache absorbs the repeated lookups (misses cached
# too); upserts refresh the local entry so an agent sees its own update
# immediately mid-conversation. Other workers converge within the TTL —
# acceptable staleness for memory documents.
_MEMORY_CACHE_TTL = 60.0
_MEMORY_CACHE_MAX = 1024
_memory_cache: dict[tuple[str, str, str], tuple[Memory | None, float]] = {}


def _cache_key(agent_id: str, scope: str, scope_key: str) -> tuple[str, str, str]:
    return (agent_id, scope, scope_key)


def _cache_put(key: tuple[str, str, str], memory: Memory | None) -> None:
    # Keys have per-user/channel/task cardinality: sweep expired entries when
    # the cache grows, and hard-reset if it is still over the cap.
    if len(_memory_cache) >= _MEMORY_CACHE_MAX:
        now = time.monotonic()
        for k in [
            k for k, v in _memory_cache.items() if now - v[1] >= _MEMORY_CACHE_TTL
        ]:
            del _memory_cache[k]
        if len(_memory_cache) >= _MEMORY_CACHE_MAX:
            _memory_cache.clear()
    _memory_cache[key] = (memory, time.monotonic())


class MemoryTable(Base):
    """One scoped memory document of an agent."""

    __tablename__: str = "memories"
    __table_args__: tuple[Index, ...] = (
        Index(
            "ix_memories_agent_scope_key",
            "agent_id",
            "scope",
            "scope_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(XID())
    )
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(
        String, nullable=False, comment="team | user | channel | cron"
    )
    scope_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="team_id / user_id / channel chat_id / cron task_id",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class Memory(BaseModel):
    """Read model + persistence helpers for scoped memories."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="Memory ID")]
    agent_id: Annotated[str, Field(description="Agent this memory belongs to")]
    scope: Annotated[str, Field(description="team | user | channel | cron")]
    scope_key: Annotated[str, Field(description="Key within the scope")]
    content: Annotated[str, Field(description="Memory document (markdown)")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def get(cls, agent_id: str, scope: str, scope_key: str) -> Memory | None:
        key = _cache_key(agent_id, scope, scope_key)
        cached = _memory_cache.get(key)
        if cached and time.monotonic() - cached[1] < _MEMORY_CACHE_TTL:
            return cached[0]
        started = time.monotonic()
        async with get_session() as db:
            stmt = select(MemoryTable).where(
                MemoryTable.agent_id == agent_id,
                MemoryTable.scope == scope,
                MemoryTable.scope_key == scope_key,
            )
            row = (await db.scalars(stmt)).first()
            memory = cls.model_validate(row) if row else None
        # Don't clobber an entry written by a concurrent upsert while we were
        # reading — our result would be the staler one.
        current = _memory_cache.get(key)
        if current and current[1] > started:
            return current[0]
        _cache_put(key, memory)
        return memory

    @classmethod
    async def upsert(
        cls, agent_id: str, scope: str, scope_key: str, content: str
    ) -> Memory:
        """Create or replace the memory document for a scope row (atomic)."""
        async with get_session() as db:
            stmt = (
                pg_insert(MemoryTable)
                .values(
                    id=str(XID()),
                    agent_id=agent_id,
                    scope=scope,
                    scope_key=scope_key,
                    content=content,
                )
                .on_conflict_do_update(
                    index_elements=["agent_id", "scope", "scope_key"],
                    set_={"content": content, "updated_at": func.now()},
                )
                .returning(MemoryTable)
            )
            row = (await db.execute(stmt)).scalar_one()
            memory = cls.model_validate(row)
            await db.commit()
        _cache_put(_cache_key(agent_id, scope, scope_key), memory)
        return memory
