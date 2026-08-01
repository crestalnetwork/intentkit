"""Scoped long-term memory for agents.

Memory rows live in the ``memories`` table (see ``intentkit.models.memory``)
keyed by (agent, scope, scope_key). This module resolves which scopes are
active for a conversation and merges new information into a scope's document
with an LLM.

Active scopes per conversation:

- sub-agent runs (``context.is_subagent``): none — memory is the entry
  agent's responsibility; sub-agents are stateless.
- ``team``: keyed by the *consuming* team (``context.team_id``; the owning
  team only when it runs its own agent). Each team talking to a public agent
  keeps its own team memory; a teamless guest has no team scope at all.
- exactly one contextual scope:
  - ``cron`` for autonomous runs, keyed by the task id;
  - ``channel`` for channel-platform threads (Telegram/Slack/Lark/...),
    keyed by the thread's chat id;
  - ``user`` for identified web/API users, keyed by the user id.
"""

import logging
from typing import NamedTuple

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import and_, or_, select

from intentkit.abstracts.graph import AgentContext
from intentkit.config.db import get_session
from intentkit.core.agent.info import attach_agent_info
from intentkit.models.agent import Agent
from intentkit.models.chat import AUTONOMOUS_CHAT_PREFIX, AuthorType
from intentkit.models.memory import Memory, MemoryTable
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

MAX_MEMORY_BYTES = 4000

_MEMORY_SYSTEM_PROMPT = f"""\
You are a memory manager. Your task is to merge existing memory with new information \
into a single consolidated memory document.

Rules:
- Keep total output under {MAX_MEMORY_BYTES} bytes.
- Use markdown with h4 (####) or lower headings only.
- Preserve important facts, remove redundant or outdated info.
- If new info contradicts old info, keep the new info.
- Output only the merged memory, no explanations or preamble."""

_CHANNEL_ENTRYPOINTS = frozenset(
    {
        AuthorType.TELEGRAM,
        AuthorType.SLACK,
        AuthorType.LARK,
        AuthorType.WECHAT,
        AuthorType.DISCORD,
    }
)


class MemoryScope(NamedTuple):
    scope: str  # team | user | channel | cron
    scope_key: str
    heading: str  # prompt section heading


def memory_owner_team(agent: Agent, context: AgentContext) -> str | None:
    """The team a conversation's team-scope memory belongs to, if any.

    The consuming team wins: a public agent visited by another team loads
    (and updates) that team's memory. The owning team's id is only used
    when the owning team itself runs the agent (legacy/local runs without a
    message team_id) — a teamless guest gets NO team scope, never the
    owning team's memory.
    """
    if context.team_id:
        return context.team_id
    if context.is_own_team:
        return agent.team_id or "system"
    return None


def resolve_memory_scopes(agent: Agent, context: AgentContext) -> list[MemoryScope]:
    """Active memory scopes for this conversation, team scope first.

    Empty for sub-agent runs: memory is owned by the entry agent, and
    delegated runs don't even carry the team context to resolve it safely.
    """
    if context.is_subagent:
        return []

    scopes = []
    team_key = memory_owner_team(agent, context)
    if team_key:
        scopes.append(MemoryScope("team", team_key, "Team Memory"))

    if context.entrypoint == AuthorType.TRIGGER:
        task_id = context.chat_id.removeprefix(AUTONOMOUS_CHAT_PREFIX)
        scopes.append(MemoryScope("cron", task_id, "Cron Task Memory"))
    elif context.entrypoint in _CHANNEL_ENTRYPOINTS:
        scopes.append(MemoryScope("channel", context.chat_id, "Channel Memory"))
    elif context.user_id:
        scopes.append(MemoryScope("user", context.user_id, "User Memory"))

    return scopes


async def merge_memory_content(existing: str, new_content: str) -> str:
    """Merge new information into an existing memory document with an LLM.

    Falls back to plain concatenation when the LLM is unavailable; the result
    is always truncated to ``MAX_MEMORY_BYTES``.
    """
    from intentkit.models.llm import create_llm_model
    from intentkit.models.llm_picker import pick_summarize_model

    if existing:
        user_msg = (
            f"### Existing Memory\n\n{existing}\n\n### New Information\n\n{new_content}"
        )
    else:
        user_msg = f"### New Information\n\n{new_content}"

    try:
        model_name = pick_summarize_model()
        # Merging memory documents needs no reasoning; "none" clamps to the
        # weakest level the picked model supports.
        llm = await create_llm_model(model_name, reasoning_effort="none")
        model = await llm.create_instance()

        response = await model.ainvoke(
            [
                SystemMessage(content=_MEMORY_SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ]
        )
        result = response.content
        if not isinstance(result, str):
            result = str(result)
    except Exception as e:
        logger.error("LLM memory merge failed: %s", e)
        # Fallback: just append
        result = f"{existing}\n\n{new_content}".strip() if existing else new_content

    encoded = result.encode("utf-8")
    if len(encoded) > MAX_MEMORY_BYTES:
        result = encoded[:MAX_MEMORY_BYTES].decode("utf-8", errors="ignore")
    return result


async def update_scoped_memory(
    agent_id: str, scope: str, scope_key: str, new_content: str
) -> str:
    """Merge ``new_content`` into one memory row and persist it."""
    memory = await Memory.get(agent_id, scope, scope_key)
    merged = await merge_memory_content(memory.content if memory else "", new_content)
    await Memory.upsert(agent_id, scope, scope_key, merged)
    return merged


class MemoryWithAgent(Memory):
    """Memory row enriched with agent display info for the management APIs."""

    agent_name: str | None = None
    agent_picture: str | None = None


def account_scopes(team_id: str, user_id: str) -> list[tuple[str, str]]:
    """The (scope, scope_key) rows an account page may list and edit.

    User-scope rows belong to the user, not the team: they are listed and
    editable under every team the user visits, because a row written by a
    cross-team public agent has no other page where the user could see it.
    """
    return [("team", team_id), ("user", user_id)]


async def list_account_memories(team_id: str, user_id: str) -> list[MemoryWithAgent]:
    """Team-scope and user-scope memory documents for an account page.

    Returns the team's memories of every agent it talks to (scope_key ==
    ``team_id``, including the lead agent's synthetic ``team-{team_id}``
    row) and the user's own memories (scope_key == ``user_id``), enriched
    with agent display info.
    """
    async with get_session() as db:
        stmt = (
            select(MemoryTable)
            .where(
                or_(
                    *(
                        and_(MemoryTable.scope == s, MemoryTable.scope_key == k)
                        for s, k in account_scopes(team_id, user_id)
                    )
                )
            )
            .order_by(MemoryTable.scope, MemoryTable.updated_at.desc())
        )
        rows = (await db.scalars(stmt)).all()
        memories = [MemoryWithAgent.model_validate(row) for row in rows]
    await attach_agent_info(memories)
    # The lead agent is synthetic (no agents row), so enrichment can't
    # resolve it; fill its display info from the team's lead config.
    lead_id = f"team-{team_id}"
    if any(m.agent_id == lead_id and m.agent_name is None for m in memories):
        from intentkit.core.lead.constants import LEAD_DEFAULT_NAME
        from intentkit.models.team import Team

        lead_config = await Team.get_lead_agent_config(team_id) or {}
        for memory in memories:
            if memory.agent_id == lead_id and memory.agent_name is None:
                memory.agent_name = lead_config.get("name", LEAD_DEFAULT_NAME)
                memory.agent_picture = lead_config.get("avatar")
    return memories


async def overwrite_memory(
    memory_id: str, content: str, *, team_id: str, user_id: str
) -> Memory:
    """Overwrite one memory document verbatim from a management UI.

    No LLM merge — the caller supplies the whole document. Editable rows
    are exactly the ones ``list_account_memories`` returns; any other row
    reads as not found so its existence doesn't leak.
    """
    memory = await Memory.get_by_id(memory_id)
    if memory is None or (memory.scope, memory.scope_key) not in account_scopes(
        team_id, user_id
    ):
        raise IntentKitAPIError(404, "MemoryNotFound", "Memory not found.")
    if len(content.encode("utf-8")) > MAX_MEMORY_BYTES:
        raise IntentKitAPIError(
            422,
            "MemoryTooLong",
            f"Memory content must be at most {MAX_MEMORY_BYTES} bytes.",
        )
    return await Memory.upsert(memory.agent_id, memory.scope, memory.scope_key, content)
