# pyright: reportPrivateUsage=false
"""Tests for team membership logic in API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response

from intentkit.utils.error import IntentKitAPIError

from app.team.team import (
    _clear_current_team_if_needed,
    leave_team_endpoint,
)


class TestLeaveTeam:
    @pytest.mark.asyncio
    async def test_owner_cannot_leave(self):
        with patch(
            "app.team.team.check_permission", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True
            with pytest.raises(IntentKitAPIError) as exc:
                await leave_team_endpoint(auth=("user-123", "team-456"))
            assert exc.value.status_code == 400
            assert exc.value.key == "OwnerCannotLeave"

    @pytest.mark.asyncio
    async def test_member_can_leave(self):
        with (
            patch(
                "app.team.team.check_permission", new_callable=AsyncMock
            ) as mock_check,
            patch("app.team.team.remove_member", new_callable=AsyncMock) as mock_remove,
            patch(
                "app.team.team._clear_current_team_if_needed", new_callable=AsyncMock
            ) as mock_clear,
        ):
            mock_check.return_value = False

            response = await leave_team_endpoint(auth=("user-123", "team-456"))

            mock_remove.assert_called_once_with("team-456", "user-123")
            mock_clear.assert_called_once_with("user-123", "team-456")
            assert isinstance(response, Response)
            assert response.body == b'{"ok":true}'


class TestClearCurrentTeamIfNeeded:
    @pytest.mark.asyncio
    async def test_clear_current_team_if_needed(self):
        mock_user = MagicMock()
        mock_user.current_team_id = "team-456"

        with (
            patch("app.team.team.User.get", new_callable=AsyncMock) as mock_get,
            patch("app.team.team.UserUpdate") as mock_update,
            patch(
                "app.team.team.invalidate_user_cache", new_callable=AsyncMock
            ) as mock_invalidate,
        ):
            mock_get.return_value = mock_user
            mock_patch = AsyncMock()
            mock_update.model_validate.return_value.patch = mock_patch

            await _clear_current_team_if_needed("user-123", "team-456")

            mock_update.model_validate.assert_called_once_with(
                {"current_team_id": None}
            )
            mock_patch.assert_called_once_with("user-123")
            mock_invalidate.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_clear_current_team_not_needed(self):
        mock_user = MagicMock()
        mock_user.current_team_id = "team-789"  # different team

        with (
            patch("app.team.team.User.get", new_callable=AsyncMock) as mock_get,
            patch("app.team.team.UserUpdate") as mock_update,
            patch(
                "app.team.team.invalidate_user_cache", new_callable=AsyncMock
            ) as mock_invalidate,
        ):
            mock_get.return_value = mock_user

            await _clear_current_team_if_needed("user-123", "team-456")

            mock_update.model_validate.assert_not_called()
            mock_invalidate.assert_not_called()
