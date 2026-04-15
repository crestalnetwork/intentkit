"""Tests for Team model."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from intentkit.models.team import Team, TeamCreate, TeamRole


@pytest.mark.asyncio
async def test_save_integrity_error_maps_to_value_error():
    """Concurrent-create race loser must surface as ValueError so the endpoint
    returns 400 "Team ID is already taken" instead of leaking a 500."""
    team_create = TeamCreate(id="my-team", name="My Team")

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock(
        side_effect=IntegrityError("INSERT ...", {}, Exception("duplicate key"))
    )
    mock_db.refresh = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("intentkit.models.team.get_session", return_value=ctx):
        with pytest.raises(ValueError, match="already taken"):
            await team_create.save("user-1")

    mock_db.refresh.assert_not_called()


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
