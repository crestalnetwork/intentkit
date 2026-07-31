"""Tests for the UpdateMemoryTool system tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException
from pydantic import ValidationError

from intentkit.abstracts.graph import AgentContext
from intentkit.core.system_tools.update_memory import (
    UpdateMemoryInput,
    UpdateMemoryTool,
)
from intentkit.models.chat import AuthorType


@pytest.fixture
def mock_context():
    """Fixture for a mocked web-user context (team + user scopes active)."""
    context = MagicMock(spec=AgentContext)
    context.agent_id = "test-agent-1"
    context.chat_id = "chat-1"
    context.user_id = "user-1"
    context.team_id = "team-1"
    context.entrypoint = AuthorType.WEB
    context.is_subagent = False
    context.is_own_team = True
    context.agent = MagicMock(team_id="team-owner")
    return context


@pytest.fixture
def mock_runtime(mock_context):
    with patch("intentkit.core.system_tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime


class TestUpdateMemoryInput:
    def test_valid_input(self):
        inp = UpdateMemoryInput(scope="team", content="Remember this fact")
        assert inp.scope == "team"
        assert inp.content == "Remember this fact"

    def test_scope_and_content_required(self):
        with pytest.raises(ValidationError):
            UpdateMemoryInput(content="x")  # pyright: ignore[reportCallIssue]
        with pytest.raises(ValidationError):
            UpdateMemoryInput(scope="team")  # pyright: ignore[reportCallIssue]

    def test_unknown_scope_rejected(self):
        with pytest.raises(ValidationError):
            UpdateMemoryInput(scope="galaxy", content="x")  # pyright: ignore[reportArgumentType]


class TestUpdateMemoryTool:
    def test_tool_metadata(self):
        tool = UpdateMemoryTool()
        assert tool.name == "update_memory"
        assert "scope" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_updates_active_scope(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_scoped_memory",
            new_callable=AsyncMock,
            return_value="Merged memory content",
        ) as mock_update:
            result = await tool._arun(scope="user", content="User prefers dark mode")

        mock_update.assert_awaited_once_with(
            "test-agent-1", "user", "user-1", "User prefers dark mode"
        )
        assert "User Memory updated successfully" in result
        assert "Merged memory content" in result

    @pytest.mark.asyncio
    async def test_team_scope_uses_consuming_team(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_scoped_memory",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_update:
            await tool._arun(scope="team", content="fact")

        mock_update.assert_awaited_once_with("test-agent-1", "team", "team-1", "fact")

    @pytest.mark.asyncio
    async def test_inactive_scope_rejected(self, mock_runtime):
        tool = UpdateMemoryTool()

        with pytest.raises(ToolException, match="not active in this conversation"):
            await tool._arun(scope="cron", content="some content")

    @pytest.mark.asyncio
    async def test_subagent_refused(self, mock_runtime, mock_context):
        mock_context.is_subagent = True
        tool = UpdateMemoryTool()

        with pytest.raises(ToolException, match="sub-agent"):
            await tool._arun(scope="team", content="some content")

    @pytest.mark.asyncio
    async def test_raises_tool_exception_on_error(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_scoped_memory",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection failed"),
        ):
            with pytest.raises(ToolException, match="Failed to update memory"):
                await tool._arun(scope="team", content="some content")
