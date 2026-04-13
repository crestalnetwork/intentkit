"""Tests for get_accessible_agent — allows public agents across teams."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.utils.error import IntentKitAPIError

from app.team.agent import get_accessible_agent


def _make_agent(
    *,
    agent_id: str = "agent-1",
    team_id: str = "team-a",
    visibility: AgentVisibility | None = AgentVisibility.TEAM,
    archived: bool = False,
):
    """Build a minimal Agent-like object for testing."""
    from unittest.mock import MagicMock

    agent = MagicMock()
    agent.id = agent_id
    agent.team_id = team_id
    agent.visibility = visibility
    agent.archived_at = datetime.now(UTC) if archived else None
    return agent


class TestGetAccessibleAgent:
    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_own_team_agent(self, mock_get):
        """Agent belonging to the team is always accessible."""
        agent = _make_agent(team_id="team-a")
        mock_get.return_value = agent
        result = await get_accessible_agent("agent-1", "team-a")
        assert result is agent

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_public_agent_from_another_team(self, mock_get):
        """Public non-archived agent from another team is accessible."""
        agent = _make_agent(team_id="predefined", visibility=AgentVisibility.PUBLIC)
        mock_get.return_value = agent
        result = await get_accessible_agent("agent-1", "team-b")
        assert result is agent

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_public_archived_agent_blocked(self, mock_get):
        """Public but archived agent from another team is NOT accessible."""
        agent = _make_agent(
            team_id="predefined",
            visibility=AgentVisibility.PUBLIC,
            archived=True,
        )
        mock_get.return_value = agent
        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_accessible_agent("agent-1", "team-b")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_private_agent_from_another_team_blocked(self, mock_get):
        """Private agent from another team is NOT accessible."""
        agent = _make_agent(team_id="team-a", visibility=AgentVisibility.PRIVATE)
        mock_get.return_value = agent
        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_accessible_agent("agent-1", "team-b")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_team_visibility_agent_from_another_team_blocked(self, mock_get):
        """TEAM-visible agent from another team is NOT accessible."""
        agent = _make_agent(team_id="team-a", visibility=AgentVisibility.TEAM)
        mock_get.return_value = agent
        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_accessible_agent("agent-1", "team-b")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_agent_not_found(self, mock_get):
        """Non-existent agent raises 404."""
        mock_get.return_value = None
        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_accessible_agent("no-such", "team-a")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.team.agent.get_agent_by_id_or_slug", new_callable=AsyncMock)
    async def test_none_visibility_blocked(self, mock_get):
        """Agent with visibility=None from another team is NOT accessible."""
        agent = _make_agent(team_id="team-a", visibility=None)
        mock_get.return_value = agent
        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_accessible_agent("agent-1", "team-b")
        assert exc_info.value.status_code == 404
