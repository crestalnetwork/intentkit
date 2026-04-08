"""Tests for Team model."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.team import Team, TeamRole


@pytest.mark.asyncio
async def test_get_by_user_returns_role():
    mock_db = MagicMock()
    now = datetime.now(UTC)

    mock_team_table = MagicMock()
    mock_team_table.id = "team-123"
    mock_team_table.name = "My Team"
    mock_team_table.avatar = None
    mock_team_table.created_at = now
    mock_team_table.updated_at = now

    mock_db.execute = AsyncMock(return_value=[(mock_team_table, TeamRole.OWNER)])

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("intentkit.models.team.get_session", return_value=ctx):
        with patch.object(Team, "model_validate") as mock_validate:
            mock_team = Team.model_construct(
                id="team-123",
                name="My Team",
                created_at=now,
                updated_at=now,
                role=None,
            )
            mock_validate.return_value = mock_team

            teams = await Team.get_by_user("user-123")

            assert len(teams) == 1
            assert teams[0].id == "team-123"
            assert teams[0].role == TeamRole.OWNER
