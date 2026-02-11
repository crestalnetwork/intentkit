from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.errors import GraphRecursionError

from intentkit.core.engine import stream_agent
from intentkit.models.agent import Agent, AgentVisibility
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import AuthorType, ChatMessageCreate


@pytest.fixture
def mock_agent():
    return Agent(
        id="agent-123",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=datetime.now(),
        updated_at=datetime.now(),
        created_at=datetime.now(),
        owner="user_1",
        skills={},
        prompt="You are a helper.",
        temperature=0.7,
        visibility=AgentVisibility.PRIVATE,
        public_info_updated_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_recursion_error_handling(mock_agent):
    """Test that GraphRecursionError is caught and returns the correct system message."""

    first_msg = ChatMessageCreate(
        id="msg_1",
        chat_id="chat_1",
        agent_id="agent-123",
        user_id="user_1",
        author_id="user_1",
        author_type=AuthorType.WEB,
        message="Hello",
    )

    mock_executor_instance = MagicMock()

    # Mock astream to raise GraphRecursionError
    async def mock_astream(*args, **kwargs):
        raise GraphRecursionError("Recursion limit reached")
        yield {}  # make it a generator

    mock_executor_instance.astream = mock_astream

    with (
        patch(
            "intentkit.core.engine.get_agent", new_callable=AsyncMock
        ) as mock_get_agent,
        patch(
            "intentkit.core.engine.agent_executor", new_callable=AsyncMock
        ) as mock_executor_func,
        patch(
            "intentkit.models.chat.ChatMessageCreate.save", new_callable=AsyncMock
        ) as mock_save,
        patch(
            "intentkit.core.engine.explain_prompt", new_callable=AsyncMock
        ) as mock_explain,
        patch("intentkit.models.llm.LLMModelInfo.get", new_callable=AsyncMock),
        patch("intentkit.config.db.engine", new=MagicMock()),
        patch("intentkit.config.db.AsyncSession", new=MagicMock()),
        patch("intentkit.core.engine.config") as mock_config,
        patch(
            "intentkit.models.chat.ChatMessageCreate.from_system_message",
            new_callable=AsyncMock,
        ) as mock_from_system,
    ):
        mock_config.payment_enabled = False
        mock_get_agent.return_value = mock_agent
        mock_executor_func.return_value = (mock_executor_instance, 0.1)
        mock_explain.return_value = "Hello"

        # Mock save for input message
        mock_saved_msg = MagicMock()
        mock_saved_msg.id = "msg_1"
        mock_saved_msg.agent_id = mock_agent.id
        mock_saved_msg.chat_id = "chat_1"
        mock_saved_msg.user_id = "user_1"
        mock_saved_msg.message = "Hello"
        mock_saved_msg.author_type = AuthorType.WEB
        mock_saved_msg.attachments = []
        mock_saved_msg.app_id = None
        mock_saved_msg.search_mode = False
        mock_saved_msg.super_mode = False
        mock_save.return_value = mock_saved_msg

        # Mock from_system_message
        mock_error_msg_create = MagicMock()
        mock_error_msg_create.save = AsyncMock()
        mock_error_msg = MagicMock()
        mock_error_msg_create.save.return_value = mock_error_msg
        mock_from_system.return_value = mock_error_msg_create

        # Run stream_agent
        results = []
        async for res in stream_agent(first_msg):
            results.append(res)

        # Verify
        mock_from_system.assert_called_with(
            SystemMessageType.RECURSION_LIMIT_EXCEEDED,
            agent_id="agent-123",
            chat_id="chat_1",
            user_id="user_1",
            author_id="agent-123",
            thread_type=AuthorType.WEB,
            reply_to="msg_1",
            time_cost=pytest.approx(0.1, abs=1.0),  # Approximate check
        )

        assert len(results) == 1
        assert results[0] == mock_error_msg
