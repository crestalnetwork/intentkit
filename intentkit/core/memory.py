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

from intentkit.abstracts.graph import AgentContext
from intentkit.models.agent import Agent
from intentkit.models.chat import AUTONOMOUS_CHAT_PREFIX, AuthorType
from intentkit.models.memory import Memory

logger = logging.getLogger(__name__)

_MEMORY_SYSTEM_PROMPT = """\
You are a memory manager. Your task is to merge existing memory with new information \
into a single consolidated memory document.

Rules:
- Keep total output under 4000 bytes.
- Use markdown with h4 (####) or lower headings only.
- Preserve important facts, remove redundant or outdated info.
- If new info contradicts old info, keep the new info.
- Output only the merged memory, no explanations or preamble."""

MAX_MEMORY_BYTES = 4000

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
        llm = await create_llm_model(model_name, temperature=0.3)
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
