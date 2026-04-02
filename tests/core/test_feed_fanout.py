"""Tests for feed fan-out with public agent visibility check."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable


@pytest.fixture
def public_agent_row():
    row = MagicMock(spec=AgentTable)
    row.id = "public-agent"
    row.visibility = AgentVisibility.PUBLIC
    return row


@pytest.fixture
def private_agent_row():
    row = MagicMock(spec=AgentTable)
    row.id = "private-agent"
    row.visibility = AgentVisibility.PRIVATE
    return row


@pytest.fixture
def null_visibility_agent_row():
    row = MagicMock(spec=AgentTable)
    row.id = "null-vis-agent"
    row.visibility = None
    return row


# ---- _resolve_target_teams tests ----


@pytest.mark.asyncio
async def test_resolve_teams_public_agent_already_subscribed(public_agent_row):
    """Public agent already subscribed to 'public' team - no duplicate."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["team1", "public"]
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = public_agent_row

    team_ids = await _resolve_target_teams(mock_session, "public-agent")

    assert "public" in team_ids
    assert team_ids.count("public") == 1  # No duplicate
    assert "team1" in team_ids


@pytest.mark.asyncio
async def test_resolve_teams_public_agent_not_subscribed(public_agent_row):
    """Public agent not yet subscribed - 'public' should be added."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["team1"]
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = public_agent_row

    team_ids = await _resolve_target_teams(mock_session, "public-agent")

    assert "public" in team_ids
    assert "team1" in team_ids
    assert len(team_ids) == 2


@pytest.mark.asyncio
async def test_resolve_teams_private_agent(private_agent_row):
    """Private agent should NOT get 'public' team added."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["team1"]
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = private_agent_row

    team_ids = await _resolve_target_teams(mock_session, "private-agent")

    assert "public" not in team_ids
    assert team_ids == ["team1"]


@pytest.mark.asyncio
async def test_resolve_teams_null_visibility(null_visibility_agent_row):
    """Agent with null visibility should NOT get 'public' team added."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = null_visibility_agent_row

    team_ids = await _resolve_target_teams(mock_session, "null-vis-agent")

    assert team_ids == []


@pytest.mark.asyncio
async def test_resolve_teams_no_subscriptions_private(private_agent_row):
    """Private agent with no subscriptions returns empty list."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = private_agent_row

    team_ids = await _resolve_target_teams(mock_session, "private-agent")

    assert team_ids == []


@pytest.mark.asyncio
async def test_resolve_teams_no_subscriptions_public(public_agent_row):
    """Public agent with no subscriptions should still get 'public' team."""
    from intentkit.core.team.feed import _resolve_target_teams

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = public_agent_row

    team_ids = await _resolve_target_teams(mock_session, "public-agent")

    assert team_ids == ["public"]


@pytest.mark.asyncio
async def test_resolve_teams_team_visibility_excluded():
    """TEAM visibility (10) is less than PUBLIC (20), should not add 'public'."""
    from intentkit.core.team.feed import _resolve_target_teams

    team_agent = MagicMock(spec=AgentTable)
    team_agent.visibility = AgentVisibility.TEAM  # 10

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["team1"]
    mock_session.execute.return_value = mock_result
    mock_session.get.return_value = team_agent

    team_ids = await _resolve_target_teams(mock_session, "team-agent")

    assert "public" not in team_ids


# ---- fan_out_activity integration tests ----


@pytest.mark.asyncio
async def test_fan_out_activity_public_agent():
    """Fan-out for public agent should include 'public' team."""
    from intentkit.core.team.feed import fan_out_activity

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["team1"]
    mock_session.execute.return_value = mock_result

    agent_row = MagicMock(spec=AgentTable)
    agent_row.visibility = AgentVisibility.PUBLIC
    mock_session.get.return_value = agent_row

    with patch("intentkit.core.team.feed.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await fan_out_activity("act-1", "public-agent", datetime.now())

    # Verify insert was called
    mock_session.execute.assert_called()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fan_out_activity_no_teams_skips():
    """Fan-out with no target teams should skip entirely."""
    from intentkit.core.team.feed import fan_out_activity

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    agent_row = MagicMock(spec=AgentTable)
    agent_row.visibility = AgentVisibility.PRIVATE
    mock_session.get.return_value = agent_row

    with patch("intentkit.core.team.feed.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await fan_out_activity("act-1", "private-agent", datetime.now())

    # commit should NOT be called when there are no teams
    mock_session.commit.assert_not_called()


# ---- fan_out_post integration tests ----


@pytest.mark.asyncio
async def test_fan_out_post_public_agent():
    """Fan-out for public agent posts should include 'public' team."""
    from intentkit.core.team.feed import fan_out_post

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    agent_row = MagicMock(spec=AgentTable)
    agent_row.visibility = AgentVisibility.PUBLIC
    mock_session.get.return_value = agent_row

    with patch("intentkit.core.team.feed.get_session") as mock_get_session:
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await fan_out_post("post-1", "public-agent", datetime.now())

    mock_session.execute.assert_called()
    mock_session.commit.assert_called_once()
