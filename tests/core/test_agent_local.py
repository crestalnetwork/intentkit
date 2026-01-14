import os
from datetime import datetime
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
from epyxid import XID
from langchain_core.tools import tool

from intentkit.core.engine import build_agent, stream_agent_raw
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import AuthorType, ChatMessage, ChatMessageCreate
from intentkit.models.llm import AVAILABLE_MODELS, LLMModelInfo, LLMProvider


def _ollama_has_model(base_url: str, model_name: str) -> bool:
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=1.0)
        if resp.status_code != 200:
            return False
        data = resp.json()
        models = data.get("models", [])
        if not isinstance(models, list):
            return False
        return any(
            model.get("name") == model_name
            for model in models
            if isinstance(model, dict)
        )
    except Exception:
        return False


# Mock the database models since we don't have a real DB in this unit test
@pytest.fixture
def mock_db_models():
    with (
        patch("intentkit.models.agent_data.AgentData.get") as mock_agent_data_get,
        patch("intentkit.models.llm.LLMModelInfo.get") as mock_llm_get,
        patch("intentkit.models.llm.create_llm_model") as mock_create_llm,
        patch("intentkit.core.engine.get_checkpointer") as mock_checkpointer,
        patch("intentkit.core.engine.get_session") as mock_session,
        patch("intentkit.core.engine.expense_message") as mock_expense,
        patch("intentkit.core.engine.expense_skill") as mock_expense_skill,
    ):
        # Setup mock session
        mock_session_ctx = MagicMock()
        mock_session.return_value.__aenter__.return_value = mock_session_ctx

        yield {
            "agent_data_get": mock_agent_data_get,
            "llm_get": mock_llm_get,
            "create_llm": mock_create_llm,
            "checkpointer": mock_checkpointer,
            "session": mock_session_ctx,
            "expense": mock_expense,
            "expense_skill": mock_expense_skill,
        }


@tool
def calculator(operation: str, a: int, b: int) -> int:
    """Perform basic arithmetic operations.

    Args:
        operation: One of 'add', 'subtract', 'multiply', 'divide'
        a: First number
        b: Second number
    """
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return int(a / b)
    return 0


@pytest.mark.asyncio
async def test_local_agent_tool_call():
    """Test that a local agent can be built and execute a tool call."""
    if os.getenv("INTENTKIT_RUN_LOCAL_LLM_TESTS") != "true":
        pytest.skip("set INTENTKIT_RUN_LOCAL_LLM_TESTS=true to run")

    # Define a local model
    local_model_id = "qwen3:0.6b"
    local_model_info = LLMModelInfo.model_construct(
        id=local_model_id,
        name=local_model_id,
        provider=LLMProvider.OLLAMA,
        enabled=True,
        input_price=0,
        output_price=0,
        context_length=32000,
        output_length=4096,
        intelligence=3,
        speed=5,
        supports_skill_calls=True,
        api_base="http://localhost:11434",
        timeout=30,
        supports_temperature=True,
        supports_frequency_penalty=True,
        supports_presence_penalty=True,
        supports_image_input=False,
        supports_structured_output=False,
        has_reasoning=False,
        supports_search=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    if not _ollama_has_model(
        local_model_info.api_base or "http://localhost:11434", local_model_id
    ):
        pytest.skip("ollama not available or model not pulled")

    # Patch AVAILABLE_MODELS to include our local model
    with patch.dict(AVAILABLE_MODELS, {local_model_id: local_model_info}):
        # 1. Setup Agent
        agent = Agent.model_construct(
            id="test-agent",
            name="Test Agent",
            model=local_model_id,
            owner="user_1",
            temperature=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            prompt="You are a helpful assistant. Use the calculator tool when asked to do math.",
            skills=None,
        )

        agent_data = AgentData.model_construct(
            id="test-agent", twitter_is_verified=False
        )

        # Mock DB returns
        with (
            patch(
                "intentkit.models.llm.LLMModelInfo.get", return_value=local_model_info
            ),
            patch("intentkit.models.agent.Agent.get", return_value=agent),
            patch("intentkit.models.agent_data.AgentData.get", return_value=agent_data),
            patch("intentkit.core.engine.get_checkpointer", side_effect=RuntimeError),
            patch("intentkit.core.engine.get_session"),
            patch("intentkit.core.engine.config.payment_enabled", False),
            patch("intentkit.models.user.User.get", return_value=None),
            patch(
                "intentkit.models.app_setting.AppSetting.error_message",
                return_value="Error occurred",
            ),
            patch("intentkit.core.engine.clear_thread_memory"),
        ):
            # 2. Build Agent with custom tool
            executor = await build_agent(agent, agent_data, custom_skills=[calculator])

            assert executor is not None

            # 3. Create a message to trigger the tool
            message = ChatMessageCreate(
                id=str(XID()),
                agent_id=agent.id,
                chat_id="test_chat",
                user_id="user_1",
                message="What is 5 plus 3?",
                author_type=AuthorType.WEB,
                author_id="user_1",
            )

            # Mock save methods
            # Mock save_in_session to return a ChatMessage with created_at
            async def mock_save_in_session(self, session):
                data = self.model_dump()
                data["created_at"] = datetime.now()
                return ChatMessage(**data)

            async def mock_save(self):
                return await mock_save_in_session(self, None)

            with (
                patch(
                    "intentkit.models.chat.ChatMessageCreate.save_in_session",
                    side_effect=mock_save_in_session,
                    autospec=True,
                ),
                patch(
                    "intentkit.models.chat.ChatMessageCreate.save",
                    side_effect=mock_save,
                    autospec=True,
                ),
            ):
                # 4. Run stream_agent_raw
                responses = []
                async for response in cast(
                    Any, stream_agent_raw(message, agent, executor)
                ):
                    responses.append(response)

            # 5. Verify results
            # We expect at least:
            # 1. Tool call message (from agent)
            # 2. Tool output message (from tool)
            # 3. Final answer message (from agent)

            has_tool_call = False
            has_tool_output = False
            final_answer = ""

            for resp in responses:
                if resp.skill_calls:
                    has_tool_call = True
                    print(f"Tool Call: {resp.skill_calls}")
                    # Verify correct tool and args
                    call = resp.skill_calls[0]
                    assert call["name"] == "calculator"
                    # Args might be parsed differently depending on model, but check basics
                    # We expect arguments to be roughly {'operation': 'add', 'a': 5, 'b': 3}
                    # Some models might return strings, so be flexible if needed, but for now expect correct types if pydantic handles it
                    args = call["parameters"]
                    assert args.get("operation") == "add"
                    assert int(args.get("a")) == 5
                    assert int(args.get("b")) == 3

                if resp.author_type == AuthorType.SKILL:
                    # This is the output of the tool
                    has_tool_output = True
                    # Check skill_calls for response
                    if resp.skill_calls:
                        for call in resp.skill_calls:
                            if call["name"] == "calculator":
                                print(f"Tool Output: {call.get('response')}")
                                assert "8" in str(call.get("response"))

                if (
                    resp.message
                    and not resp.skill_calls
                    and resp.author_type == AuthorType.AGENT
                ):
                    final_answer += resp.message

            print(f"Final Answer: {final_answer}")

            assert has_tool_call, "Agent did not call the tool"
            assert has_tool_output, "Agent did not receive tool output"
            # assert "8" in final_answer # Final answer might vary, but tool call is the critical part for this test


@pytest.mark.asyncio
async def test_local_agent_system_tool_call():
    """Test that a local agent can be built and execute a system tool call (current_time)."""
    if os.getenv("INTENTKIT_RUN_LOCAL_LLM_TESTS") != "true":
        pytest.skip("set INTENTKIT_RUN_LOCAL_LLM_TESTS=true to run")

    # Define a local model
    local_model_id = "qwen3:0.6b"
    local_model_info = LLMModelInfo.model_construct(
        id=local_model_id,
        name=local_model_id,
        provider=LLMProvider.OLLAMA,
        enabled=True,
        input_price=0,
        output_price=0,
        context_length=32000,
        output_length=4096,
        intelligence=3,
        speed=5,
        supports_skill_calls=True,
        api_base="http://localhost:11434",
        timeout=30,
        supports_temperature=True,
        supports_frequency_penalty=True,
        supports_presence_penalty=True,
        supports_image_input=False,
        supports_structured_output=False,
        has_reasoning=False,
        supports_search=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    if not _ollama_has_model(
        local_model_info.api_base or "http://localhost:11434", local_model_id
    ):
        pytest.skip("ollama not available or model not pulled")

    # Patch AVAILABLE_MODELS to include our local model
    with patch.dict(AVAILABLE_MODELS, {local_model_id: local_model_info}):
        # 1. Setup Agent
        agent = Agent.model_construct(
            id="test-agent-system",
            name="Test Agent System",
            model=local_model_id,
            owner="user_1",
            temperature=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            prompt="You are a helpful assistant. Use the common_current_time tool when asked for the time.",
            skills={
                "common": {
                    "enabled": True,
                    "states": {"current_time": "public"},
                }
            },
        )

        agent_data = AgentData.model_construct(
            id="test-agent-system", twitter_is_verified=False
        )

        # Mock DB returns
        with (
            patch(
                "intentkit.models.llm.LLMModelInfo.get", return_value=local_model_info
            ),
            patch("intentkit.models.agent.Agent.get", return_value=agent),
            patch("intentkit.models.agent_data.AgentData.get", return_value=agent_data),
            patch("intentkit.core.engine.get_checkpointer", side_effect=RuntimeError),
            patch("intentkit.core.engine.get_session"),
            patch("intentkit.core.engine.config.payment_enabled", False),
            patch("intentkit.models.user.User.get", return_value=None),
            patch(
                "intentkit.models.app_setting.AppSetting.error_message",
                return_value="Error occurred",
            ),
            patch("intentkit.core.engine.clear_thread_memory"),
        ):
            # 2. Build Agent with system tool
            # Note: build_agent accepts custom_skills, we can pass the initialized tool instance
            executor = await build_agent(agent, agent_data)

            assert executor is not None

            # 3. Create a message to trigger the tool
            message = ChatMessageCreate(
                id=str(XID()),
                agent_id=agent.id,
                chat_id="test_chat_system",
                user_id="user_1",
                message="What time is it in UTC?",
                author_type=AuthorType.WEB,
                author_id="user_1",
            )

            # Mock save methods
            # Mock save_in_session to return a ChatMessage with created_at
            async def mock_save_in_session(self, session):
                data = self.model_dump()
                data["created_at"] = datetime.now()
                return ChatMessage(**data)

            async def mock_save(self):
                return await mock_save_in_session(self, None)

            with (
                patch(
                    "intentkit.models.chat.ChatMessageCreate.save_in_session",
                    side_effect=mock_save_in_session,
                    autospec=True,
                ),
                patch(
                    "intentkit.models.chat.ChatMessageCreate.save",
                    side_effect=mock_save,
                    autospec=True,
                ),
            ):
                # 4. Run stream_agent_raw
                responses = []
                async for response in cast(
                    Any, stream_agent_raw(message, agent, executor)
                ):
                    responses.append(response)

            # 5. Verify results
            has_tool_call = False
            has_tool_output = False
            final_answer = ""

            for resp in responses:
                if resp.skill_calls:
                    has_tool_call = True
                    print(f"Tool Call: {resp.skill_calls}")
                    # Verify correct tool
                    call = resp.skill_calls[0]
                    assert call["name"] == "common_current_time"

                if resp.author_type == AuthorType.SKILL:
                    # This is the output of the tool
                    has_tool_output = True
                    # Check skill_calls for response
                    if resp.skill_calls:
                        for call in resp.skill_calls:
                            if call["name"] == "common_current_time":
                                print(f"Tool Output: {call.get('response')}")
                                assert "Current time:" in str(call.get("response"))

                if (
                    resp.message
                    and not resp.skill_calls
                    and resp.author_type == AuthorType.AGENT
                ):
                    final_answer += resp.message

            print(f"Final Answer: {final_answer}")

            assert has_tool_call, "Agent did not call the tool"
            assert has_tool_output, "Agent did not receive tool output"
