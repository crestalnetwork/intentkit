"""
BDD Tests: Core Engine Conversation Flow

Feature: Agent Conversation Lifecycle
As an IntentKit operator, I want to verify that the core engine correctly
handles conversations end-to-end, including chat message persistence,
credit event recording, and skill invocations.

Model: openrouter/free (rate limit: 20 req/min, budget: ≤20 LLM requests total)
"""

import re
from typing import Any

import pytest
from sqlalchemy import desc, select

from intentkit.config.db import get_session
from intentkit.core.agent import create_agent
from intentkit.core.engine import execute_agent
from intentkit.models.agent import AgentCreate
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageTable,
)
from intentkit.models.credit import CreditEventTable, EventType
from intentkit.utils.error import IntentKitAPIError

# Use session-scoped event loop to share DB connections across tests
pytestmark = pytest.mark.asyncio(loop_scope="session")

# Common model for all tests
MODEL = "openrouter/free"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def query_chat_messages(agent_id: str, chat_id: str) -> list[ChatMessage]:
    """Query all chat messages for a given agent and chat from DB."""
    async with get_session() as db:
        results = await db.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
            )
            .order_by(ChatMessageTable.created_at)
        )
        return [ChatMessage.model_validate(r) for r in results]


async def query_credit_events(
    agent_id: str,
    event_type: str | None = None,
) -> list[Any]:
    """Query credit events for a given agent from DB."""
    async with get_session() as db:
        stmt = select(CreditEventTable).where(
            CreditEventTable.agent_id == agent_id,
        )
        if event_type:
            stmt = stmt.where(CreditEventTable.event_type == event_type)
        stmt = stmt.order_by(desc(CreditEventTable.created_at))
        results = await db.scalars(stmt)
        return list(results)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@pytest.mark.bdd
async def test_simple_conversation() -> None:
    """
    Scenario: Simple Conversation Without Skills

    Given a deployed agent with `model=openrouter/free` and no skills
    When a user sends "Hello, who are you?"
    Then the engine returns at least one agent reply message
    And the user input message is persisted in the database
    And the agent reply message is persisted in the database
    And a credit event of type `message` is created
    And the agent reply message has `credit_event_id` set

    LLM Requests: ~1
    """
    # Given
    agent_input = AgentCreate(
        id="engine-simple-1",
        name="Simple Conversation Agent",
        model=MODEL,
        owner="system",
        prompt="You are a helpful assistant. Reply concisely.",
    )
    await create_agent(agent_input)

    # When
    message = ChatMessageCreate(
        id="msg-simple-in-1",
        agent_id="engine-simple-1",
        chat_id="chat-simple-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="Hello, who are you?",
    )
    responses = await execute_agent(message)

    # Then — check returned responses
    assert len(responses) >= 1
    agent_replies = [r for r in responses if r.author_type == AuthorType.AGENT]
    assert len(agent_replies) >= 1
    assert agent_replies[0].message  # Non-empty reply

    # Then — check persistence in DB
    db_messages = await query_chat_messages("engine-simple-1", "chat-simple-1")
    # At minimum: 1 user input + 1 agent reply
    assert len(db_messages) >= 2

    user_msgs = [m for m in db_messages if m.author_type == AuthorType.WEB]
    agent_msgs = [m for m in db_messages if m.author_type == AuthorType.AGENT]
    assert len(user_msgs) >= 1
    assert len(agent_msgs) >= 1

    # Then — check credit events
    credit_events = await query_credit_events("engine-simple-1", EventType.MESSAGE)
    assert len(credit_events) >= 1

    # Then — agent reply message has credit_event_id
    assert agent_replies[0].credit_event_id is not None


@pytest.mark.bdd
async def test_skill_call_current_time() -> None:
    """
    Scenario: Skill Call (common_current_time)

    Given a deployed agent with `model=openrouter/free` and `common` skill enabled
    When a user sends "What is the current time in UTC?"
    Then the engine returns messages including a skill call message
    And the skill call message contains `common_current_time` with `success=True`
    And the skill call response contains a date-like string
    And credit events include both `message` and `skill_call` types
    And the agent final reply contains time information

    LLM Requests: ~2 (1 tool-call decision + 1 final reply)
    """
    # Given
    agent_input = AgentCreate(
        id="engine-skill-1",
        name="Skill Agent",
        model=MODEL,
        owner="system",
        prompt="You are a helpful assistant. When asked about time, use the current_time tool. Reply concisely.",
        skills={
            "common": {
                "enabled": True,
                "states": {
                    "current_time": "public",
                },
            },
        },
    )
    await create_agent(agent_input)

    # When
    message = ChatMessageCreate(
        id="msg-skill-in-1",
        agent_id="engine-skill-1",
        chat_id="chat-skill-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="What is the current time in UTC?",
    )
    responses = await execute_agent(message)

    # Then — check that responses include skill call
    assert len(responses) >= 2
    skill_msgs = [r for r in responses if r.author_type == AuthorType.SKILL]
    assert len(skill_msgs) >= 1, "Expected at least one skill call message"

    # Then — check skill call details
    skill_msg = skill_msgs[0]
    assert skill_msg.skill_calls is not None
    assert len(skill_msg.skill_calls) >= 1

    time_call = None
    for call in skill_msg.skill_calls:
        if call["name"] == "common_current_time":
            time_call = call
            break
    assert time_call is not None, "Expected common_current_time skill call"
    assert time_call["success"] is True
    # Response should contain a date pattern like "2026-02-10"
    assert re.search(r"\d{4}-\d{2}-\d{2}", time_call.get("response", ""))

    # Then — check agent final reply
    agent_replies = [r for r in responses if r.author_type == AuthorType.AGENT]
    assert len(agent_replies) >= 1

    # Then — check credit events
    message_events = await query_credit_events("engine-skill-1", EventType.MESSAGE)
    skill_events = await query_credit_events("engine-skill-1", EventType.SKILL_CALL)
    assert len(message_events) >= 1, "Expected at least one message credit event"
    assert len(skill_events) >= 1, "Expected at least one skill call credit event"


@pytest.mark.bdd
async def test_multi_turn_conversation() -> None:
    """
    Scenario: Multi-turn Conversation with Memory

    Given a deployed agent with `model=openrouter/free`
    When user sends "My name is TestUser" and then "What is my name?"
    Then the second response contains "TestUser" (memory works)
    And both turns produce chat messages in the database
    And credit events are created for both turns

    LLM Requests: ~2 (1 per turn)
    """
    # Given
    agent_input = AgentCreate(
        id="engine-multi-1",
        name="Multi-turn Agent",
        model=MODEL,
        owner="system",
        prompt="You are a helpful assistant. Remember what the user tells you. Reply concisely.",
    )
    await create_agent(agent_input)

    # When — Turn 1
    message1 = ChatMessageCreate(
        id="msg-multi-in-1",
        agent_id="engine-multi-1",
        chat_id="chat-multi-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="My name is TestUser",
    )
    responses1 = await execute_agent(message1)
    assert len(responses1) >= 1

    # When — Turn 2
    message2 = ChatMessageCreate(
        id="msg-multi-in-2",
        agent_id="engine-multi-1",
        chat_id="chat-multi-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="What is my name?",
    )
    responses2 = await execute_agent(message2)

    # Then — second response should contain "TestUser"
    agent_replies2 = [r for r in responses2 if r.author_type == AuthorType.AGENT]
    assert len(agent_replies2) >= 1
    combined_text = " ".join(r.message for r in agent_replies2)
    assert "TestUser" in combined_text, (
        f"Expected 'TestUser' in agent reply, got: {combined_text}"
    )

    # Then — check all messages persisted
    db_messages = await query_chat_messages("engine-multi-1", "chat-multi-1")
    # 2 user inputs + 2 agent replies = 4 minimum
    assert len(db_messages) >= 4

    # Then — check credit events for both turns
    credit_events = await query_credit_events("engine-multi-1", EventType.MESSAGE)
    assert len(credit_events) >= 2, "Expected credit events for both turns"


@pytest.mark.bdd
async def test_clear_memory_command() -> None:
    """
    Scenario: Clear Memory Command

    Given a deployed agent
    When a user sends "@clear"
    Then the engine returns a single message saying memory has been cleared
    And the reply has `author_type=agent`
    And no credit events are created (no LLM invocation)

    LLM Requests: 0
    """
    # Given
    agent_input = AgentCreate(
        id="engine-clear-1",
        name="Clear Memory Agent",
        model=MODEL,
        owner="system",
    )
    await create_agent(agent_input)

    # When
    message = ChatMessageCreate(
        id="msg-clear-in-1",
        agent_id="engine-clear-1",
        chat_id="chat-clear-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="@clear",
    )
    responses = await execute_agent(message)

    # Then
    assert len(responses) == 1
    assert responses[0].author_type == AuthorType.AGENT
    assert "cleared" in responses[0].message.lower()

    # Then — no credit events (no LLM call)
    credit_events = await query_credit_events("engine-clear-1")
    assert len(credit_events) == 0


@pytest.mark.bdd
async def test_nonexistent_agent_fails() -> None:
    """
    Scenario: Conversation with Nonexistent Agent Fails

    Given no agent with `id=nonexistent-engine-agent`
    When calling `execute_agent` with this agent_id
    Then an `IntentKitAPIError` with `status_code=404` is raised

    LLM Requests: 0
    """
    message = ChatMessageCreate(
        id="msg-nonexist-in-1",
        agent_id="nonexistent-engine-agent",
        chat_id="chat-nonexistent-1",
        user_id="system",
        author_id="system",
        author_type=AuthorType.WEB,
        message="Hello",
    )

    with pytest.raises(IntentKitAPIError) as exc_info:
        await execute_agent(message)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "AgentNotFound"
