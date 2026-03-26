from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.models.team_feed import TeamSubscription
from intentkit.utils.error import IntentKitAPIError

NOW = datetime.now(timezone.utc)

MODULE = "intentkit.core.team.subscription"


def _make_mock_session():
    """Create a mock async session with context manager support."""
    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_session, mock_ctx


def _make_mock_agent(
    team_id: str, visibility: AgentVisibility = AgentVisibility.PUBLIC
):
    """Create a mock agent with team_id and visibility."""
    agent = MagicMock()
    agent.team_id = team_id
    agent.visibility = visibility
    return agent


# ---------- subscribe_agent ----------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
async def test_subscribe_agent_not_found(mock_get_agent):
    from intentkit.core.team.subscription import subscribe_agent

    mock_get_agent.return_value = None

    with pytest.raises(IntentKitAPIError) as exc_info:
        await subscribe_agent("team-1", "agent-404")

    assert exc_info.value.status_code == 404
    mock_get_agent.assert_awaited_once_with("agent-404")


@pytest.mark.asyncio
@patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
async def test_subscribe_agent_private_different_team(mock_get_agent):
    from intentkit.core.team.subscription import subscribe_agent

    mock_get_agent.return_value = _make_mock_agent(
        "other-team", AgentVisibility.PRIVATE
    )

    with pytest.raises(IntentKitAPIError) as exc_info:
        await subscribe_agent("team-1", "agent-private")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
@patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
async def test_subscribe_agent_public_success(mock_get_agent, mock_get_session):
    from intentkit.core.team.subscription import subscribe_agent

    mock_get_agent.return_value = _make_mock_agent("other-team", AgentVisibility.PUBLIC)
    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    # Mock the second execute (select) to return a row for model_validate
    mock_row = MagicMock()
    mock_row.team_id = "team-1"
    mock_row.agent_id = "agent-pub"
    mock_row.subscribed_at = "2026-01-01T00:00:00"

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_row
    # First execute is insert, second is select
    mock_session.execute = AsyncMock(side_effect=[MagicMock(), mock_result])

    with patch.object(
        TeamSubscription,
        "model_validate",
        return_value=TeamSubscription(
            team_id="team-1", agent_id="agent-pub", subscribed_at=NOW
        ),
    ):
        result = await subscribe_agent("team-1", "agent-pub")

    assert result.team_id == "team-1"
    assert result.agent_id == "agent-pub"
    assert mock_session.execute.await_count == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
@patch(f"{MODULE}.get_agent", new_callable=AsyncMock)
async def test_subscribe_agent_same_team_success(mock_get_agent, mock_get_session):
    from intentkit.core.team.subscription import subscribe_agent

    # Private agent but same team — should succeed
    mock_get_agent.return_value = _make_mock_agent("team-1", AgentVisibility.PRIVATE)
    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    mock_row = MagicMock()
    mock_row.team_id = "team-1"
    mock_row.agent_id = "agent-own"
    mock_row.subscribed_at = NOW

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_row
    mock_session.execute = AsyncMock(side_effect=[MagicMock(), mock_result])

    with patch.object(
        TeamSubscription,
        "model_validate",
        return_value=TeamSubscription(
            team_id="team-1", agent_id="agent-own", subscribed_at=NOW
        ),
    ):
        result = await subscribe_agent("team-1", "agent-own")

    assert result.team_id == "team-1"
    assert result.agent_id == "agent-own"
    mock_session.commit.assert_awaited_once()


# ---------- unsubscribe_agent ----------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_unsubscribe_agent_success(mock_get_session):
    from intentkit.core.team.subscription import unsubscribe_agent

    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    await unsubscribe_agent("team-1", "agent-1")

    # 3 delete statements executed
    assert mock_session.execute.await_count == 3
    mock_session.commit.assert_awaited_once()


# ---------- get_subscriptions ----------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_get_subscriptions_returns_list(mock_get_session):
    from intentkit.core.team.subscription import get_subscriptions

    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    mock_row_1 = MagicMock()
    mock_row_2 = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_row_1, mock_row_2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    sub1 = TeamSubscription(team_id="team-1", agent_id="a1", subscribed_at=NOW)
    sub2 = TeamSubscription(team_id="team-1", agent_id="a2", subscribed_at=NOW)

    with patch.object(TeamSubscription, "model_validate", side_effect=[sub1, sub2]):
        result = await get_subscriptions("team-1")

    assert len(result) == 2
    assert result[0].agent_id == "a1"
    assert result[1].agent_id == "a2"


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_get_subscriptions_empty(mock_get_session):
    from intentkit.core.team.subscription import get_subscriptions

    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_subscriptions("team-1")

    assert result == []


# ---------- auto_subscribe_team ----------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_auto_subscribe_team_success(mock_get_session):
    from intentkit.core.team.subscription import auto_subscribe_team

    mock_session, mock_ctx = _make_mock_session()
    mock_get_session.return_value = mock_ctx

    await auto_subscribe_team("team-1", "agent-1")

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
