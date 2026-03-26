"""Tests for intentkit.core.lead.service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.utils.error import IntentKitAPIError

MODULE = "intentkit.core.lead.service"


def _mock_session():
    """Create a mock async context manager that yields a mock db session."""
    db = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, db


def _mock_agent_row(
    agent_id="agent-1",
    team_id="team-1",
    name="Test Agent",
):
    """Create a MagicMock that looks like an AgentTable row."""
    row = MagicMock()
    row.id = agent_id
    row.team_id = team_id
    row.name = name
    row.description = "desc"
    row.model = "gpt-4o"
    row.prompt = "You are helpful."
    row.skills = {}
    row.temperature = 0.7
    row.owner = "owner-1"
    row.visibility = "private"
    now = datetime.now()
    row.created_at = now
    row.updated_at = now
    row.deployed_at = now
    row.archived_at = None
    row.public_info_updated_at = now
    return row


# ---------------------------------------------------------------------------
# verify_team_membership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_team_membership_member_exists():
    cm, db = _mock_session()
    db.scalar = AsyncMock(return_value=MagicMock())  # member found

    with patch(f"{MODULE}.get_session", return_value=cm):
        from intentkit.core.lead.service import verify_team_membership

        # Should not raise
        await verify_team_membership("team-1", "user-1")


@pytest.mark.asyncio
async def test_verify_team_membership_not_found():
    cm, db = _mock_session()
    db.scalar = AsyncMock(return_value=None)  # member not found

    with patch(f"{MODULE}.get_session", return_value=cm):
        from intentkit.core.lead.service import verify_team_membership

        with pytest.raises(IntentKitAPIError) as exc_info:
            await verify_team_membership("team-1", "user-1")

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# get_team_agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_team_agents_returns_agents():
    cm, db = _mock_session()

    row1 = _mock_agent_row(agent_id="a1", team_id="team-1", name="Agent 1")
    row2 = _mock_agent_row(agent_id="a2", team_id="team-1", name="Agent 2")

    mock_scalars_result = MagicMock()
    mock_scalars_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
    db.scalars = AsyncMock(return_value=mock_scalars_result)

    with (
        patch(f"{MODULE}.get_session", return_value=cm),
        patch(f"{MODULE}.Agent") as MockAgent,
    ):
        mock_agent_1 = MagicMock()
        mock_agent_2 = MagicMock()
        MockAgent.model_validate = MagicMock(side_effect=[mock_agent_1, mock_agent_2])

        from intentkit.core.lead.service import get_team_agents

        result = await get_team_agents("team-1")

    assert len(result) == 2
    assert result[0] is mock_agent_1
    assert result[1] is mock_agent_2


@pytest.mark.asyncio
async def test_get_team_agents_empty():
    cm, db = _mock_session()

    mock_scalars_result = MagicMock()
    mock_scalars_result.__iter__ = MagicMock(return_value=iter([]))
    db.scalars = AsyncMock(return_value=mock_scalars_result)

    with patch(f"{MODULE}.get_session", return_value=cm):
        from intentkit.core.lead.service import get_team_agents

        result = await get_team_agents("team-1")

    assert result == []


# ---------------------------------------------------------------------------
# get_team_with_members
# ---------------------------------------------------------------------------


MEMBERSHIP_MODULE = "intentkit.core.team.membership"


@pytest.mark.asyncio
async def test_get_team_with_members_team_not_found():
    with (
        patch(
            f"{MEMBERSHIP_MODULE}.get_team", new_callable=AsyncMock, return_value=None
        ),
        patch(f"{MEMBERSHIP_MODULE}.get_members", new_callable=AsyncMock),
    ):
        from intentkit.core.lead.service import get_team_with_members

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_team_with_members("no-team")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_team_with_members_success():
    now = datetime.now()

    mock_team = MagicMock()
    mock_team.id = "team-1"
    mock_team.name = "My Team"
    mock_team.avatar = "https://example.com/avatar.png"
    mock_team.created_at = now

    mock_member = MagicMock()
    mock_member.model_dump = MagicMock(
        return_value={"user_id": "u1", "role": "admin", "joined_at": now.isoformat()}
    )

    with (
        patch(
            f"{MEMBERSHIP_MODULE}.get_team",
            new_callable=AsyncMock,
            return_value=mock_team,
        ),
        patch(
            f"{MEMBERSHIP_MODULE}.get_members",
            new_callable=AsyncMock,
            return_value=[mock_member],
        ),
    ):
        from intentkit.core.lead.service import get_team_with_members

        result = await get_team_with_members("team-1")

    assert result["id"] == "team-1"
    assert result["name"] == "My Team"
    assert result["avatar"] == "https://example.com/avatar.png"
    assert result["created_at"] == now.isoformat()
    assert len(result["members"]) == 1
    mock_member.model_dump.assert_called_once_with(mode="json")


# ---------------------------------------------------------------------------
# verify_agent_in_team
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_agent_in_team_not_found():
    cm, db = _mock_session()
    db.get = AsyncMock(return_value=None)

    with patch(f"{MODULE}.get_session", return_value=cm):
        from intentkit.core.lead.service import verify_agent_in_team

        with pytest.raises(IntentKitAPIError) as exc_info:
            await verify_agent_in_team("agent-1", "team-1")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_verify_agent_in_team_wrong_team():
    cm, db = _mock_session()
    row = _mock_agent_row(agent_id="agent-1", team_id="team-other")
    db.get = AsyncMock(return_value=row)

    with patch(f"{MODULE}.get_session", return_value=cm):
        from intentkit.core.lead.service import verify_agent_in_team

        with pytest.raises(IntentKitAPIError) as exc_info:
            await verify_agent_in_team("agent-1", "team-1")

        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_agent_in_team_success():
    cm, db = _mock_session()
    row = _mock_agent_row(agent_id="agent-1", team_id="team-1")
    db.get = AsyncMock(return_value=row)

    mock_agent = MagicMock()

    with (
        patch(f"{MODULE}.get_session", return_value=cm),
        patch(f"{MODULE}.Agent") as MockAgent,
    ):
        MockAgent.model_validate = MagicMock(return_value=mock_agent)

        from intentkit.core.lead.service import verify_agent_in_team

        result = await verify_agent_in_team("agent-1", "team-1")

    assert result is mock_agent
    MockAgent.model_validate.assert_called_once_with(row)
