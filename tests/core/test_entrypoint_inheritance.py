"""Entrypoint inheritance and sub-agent marker.

The original user entry channel (web, telegram, trigger, ...) must survive
call_agent delegation at any depth: sub-agent input messages carry it in
``thread_type`` while their ``author_type`` is INTERNAL, and the runtime
``AgentContext.entrypoint`` is rebuilt from ``thread_entrypoint`` rather than
``author_type``. "Am I a sub-agent" is a separate marker derived from
``call_depth``, never encoded in the entrypoint.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.engine import stream as stream_mod
from intentkit.core.engine.stream import build_stream_config
from intentkit.core.lead.tools.call_agent import LeadCallAgent
from intentkit.core.prompt import build_entrypoint_prompt, build_system_prompt
from intentkit.models.agent import Agent, AgentData, AgentVisibility
from intentkit.models.chat import AuthorType, ChatMessageCreate


def _agent() -> Agent:
    now = datetime.now()
    return Agent(
        id="agent-1",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=now,
        updated_at=now,
        created_at=now,
        owner="user_1",
        tools=None,
        system_prompt="You are a helper.",
        visibility=AgentVisibility.PRIVATE,
        public_info_updated_at=now,
    )


def _message(
    author_type: AuthorType,
    thread_type: AuthorType | None = None,
    call_depth: int = 0,
) -> ChatMessageCreate:
    return ChatMessageCreate(
        id="msg_1",
        agent_id="agent-1",
        chat_id="chat_1",
        user_id="user_1",
        author_id="user_1",
        author_type=author_type,
        thread_type=thread_type,
        message="hello",
        call_depth=call_depth,
    )


def _context(
    entrypoint: AuthorType = AuthorType.WEB,
    chat_id: str = "chat_1",
    call_depth: int = 0,
) -> AgentContext:
    agent = _agent()
    return AgentContext(
        agent_id=agent.id,
        get_agent=lambda: agent,
        chat_id=chat_id,
        entrypoint=entrypoint,
        is_own_team=True,
        call_depth=call_depth,
    )


def test_thread_entrypoint_prefers_thread_type():
    """Sub-agent input messages resolve to the inherited channel, not INTERNAL."""
    message = _message(AuthorType.INTERNAL, thread_type=AuthorType.TELEGRAM)
    assert message.thread_entrypoint == AuthorType.TELEGRAM.value


def test_thread_entrypoint_falls_back_to_author_type():
    message = _message(AuthorType.WEB)
    assert message.thread_entrypoint == AuthorType.WEB.value


def test_is_subagent_derived_from_call_depth():
    assert _context().is_subagent is False
    assert _context(call_depth=1).is_subagent is True


def test_lead_call_agent_message_inherits_entrypoint():
    """thread_type must carry the original entrypoint at any call depth."""
    context = _context(entrypoint=AuthorType.TELEGRAM, call_depth=1)
    message = LeadCallAgent._build_chat_message(
        context, "target-agent", "team-1", "do something", None
    )
    assert message.author_type == AuthorType.INTERNAL.value
    assert message.thread_type == AuthorType.TELEGRAM.value
    assert message.call_depth == 2
    # The next hop's context rebuilds the same entrypoint from this message.
    assert message.thread_entrypoint == AuthorType.TELEGRAM.value


def test_stream_config_marks_subagent_and_inherited_channel(monkeypatch):
    monkeypatch.setattr(stream_mod.config, "langfuse_tracing", True)
    agent = _agent()
    message = _message(
        AuthorType.INTERNAL, thread_type=AuthorType.TELEGRAM, call_depth=1
    )

    stream_config = build_stream_config(message, agent, None, "agent-1-chat_1")

    metadata = stream_config.get("metadata") or {}
    assert metadata["channel"] == AuthorType.TELEGRAM.value
    assert metadata["is_subagent"] is True
    assert "subagent" in metadata["langfuse_tags"]


def test_stream_config_top_level_has_no_subagent_marker(monkeypatch):
    monkeypatch.setattr(stream_mod.config, "langfuse_tracing", True)
    agent = _agent()
    message = _message(AuthorType.WEB, thread_type=AuthorType.WEB)

    stream_config = build_stream_config(message, agent, None, "agent-1-chat_1")

    metadata = stream_config.get("metadata") or {}
    assert metadata["channel"] == AuthorType.WEB.value
    assert "is_subagent" not in metadata
    assert "subagent" not in metadata["langfuse_tags"]


@pytest.mark.asyncio
async def test_trigger_entrypoint_subagent_skips_task_lookup():
    """A sub-agent of an autonomous run gets the no-user-interaction rule only.

    Its chat_id is a throwaway call-xxx id, so the task lookup would fail and
    inject a misleading "task id is call-xxx" prompt.
    """
    agent = _agent()
    context = _context(entrypoint=AuthorType.TRIGGER, chat_id="call-xyz", call_depth=1)

    result = await build_entrypoint_prompt(agent, context)

    assert result is not None
    assert "cannot ask the user" in result.lower()
    assert "call-xyz" not in result


@pytest.mark.asyncio
async def test_system_prompt_subagent_mode_section():
    agent = _agent()
    agent_data = AgentData(
        id=agent.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # The top-level prompt loads scoped memories; keep this test off the DB.
    with patch(
        "intentkit.models.memory.Memory.get",
        new=AsyncMock(return_value=None),
    ):
        subagent_prompt = await build_system_prompt(
            agent, agent_data, _context(call_depth=1)
        )
        top_level_prompt = await build_system_prompt(agent, agent_data, _context())

    assert "## Sub-agent Mode" in subagent_prompt
    assert "## Sub-agent Mode" not in top_level_prompt
