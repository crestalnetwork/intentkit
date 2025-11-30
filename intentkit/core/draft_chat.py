"""Utilities for streaming draft agent conversations."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.engine import build_agent, stream_agent_raw
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import ChatMessage, ChatMessageCreate
from intentkit.models.db import get_session
from intentkit.models.draft import AgentDraft, AgentDraftTable
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


_draft_executors: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}
_draft_updated_at: dict[str, datetime] = {}
_draft_cached_at: dict[str, datetime] = {}

_CACHE_TTL = timedelta(days=1)


async def stream_draft(
    agent_id: str, message: ChatMessageCreate
) -> AsyncGenerator[ChatMessage, None]:
    """Stream chat messages for the latest draft of an agent."""

    draft = await _get_latest_draft(agent_id)
    agent = _agent_from_draft(draft)
    executor, cold_start_cost = await _get_draft_executor(agent, draft)

    if not message.agent_id:
        message.agent_id = agent.id
    message.cold_start_cost = cold_start_cost

    async for chat_message in stream_agent_raw(message, agent, executor):
        yield chat_message


async def _get_latest_draft(agent_id: str) -> AgentDraft:
    async with get_session() as session:
        result = await _execute_latest_draft_query(session, agent_id)
        draft_row = result.scalar_one_or_none()

    if not draft_row:
        raise IntentKitAPIError(
            status_code=404,
            key="DraftNotFound",
            message=f"No draft found for agent {agent_id}",
        )

    return AgentDraft.model_validate(draft_row)


async def _execute_latest_draft_query(session: AsyncSession, agent_id: str):
    statement = (
        select(AgentDraftTable)
        .where(AgentDraftTable.agent_id == agent_id)
        .order_by(desc(AgentDraftTable.updated_at))
        .limit(1)
    )
    return await session.execute(statement)


def _agent_from_draft(draft: AgentDraft) -> Agent:
    data = draft.model_dump()
    data.pop("id", None)
    data.pop("agent_id", None)
    data.pop("last_draft_id", None)
    data["id"] = draft.agent_id
    data["owner"] = draft.owner
    data["deployed_at"] = draft.deployed_at
    data["created_at"] = draft.created_at
    data["updated_at"] = draft.updated_at
    data["version"] = draft.version
    return Agent.model_validate(data)


async def _get_draft_executor(
    agent: Agent, draft: AgentDraft
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], float]:
    now = datetime.now(timezone.utc)
    _cleanup_cache(now)

    cached_executor = _draft_executors.get(agent.id)
    cached_updated = _draft_updated_at.get(agent.id)
    cold_start_cost = 0.0

    if not cached_executor or cached_updated != draft.updated_at:
        start = time.perf_counter()
        agent_data = AgentData(id=agent.id)
        cached_executor = await build_agent(agent, agent_data)
        cold_start_cost = time.perf_counter() - start
        _draft_executors[agent.id] = cached_executor
        _draft_updated_at[agent.id] = draft.updated_at
        _draft_cached_at[agent.id] = now
        logger.info("Initialized draft executor for agent %s", agent.id)
    else:
        _draft_cached_at[agent.id] = now

    return cached_executor, cold_start_cost


def _cleanup_cache(now: datetime) -> None:
    expired_before = now - _CACHE_TTL
    for agent_id, cached_time in list(_draft_cached_at.items()):
        if cached_time < expired_before:
            _draft_cached_at.pop(agent_id, None)
            _draft_updated_at.pop(agent_id, None)
            _draft_executors.pop(agent_id, None)
            logger.debug("Removed expired draft executor for agent %s", agent_id)
