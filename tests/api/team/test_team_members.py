# pyright: reportPrivateUsage=false
"""Tests for team membership logic in API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response

from intentkit.utils.error import IntentKitAPIError

from app.team.team import (
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
        ):
            mock_check.return_value = False

            response = await leave_team_endpoint(auth=("user-123", "team-456"))

            mock_remove.assert_called_once_with("team-456", "user-123")
            assert isinstance(response, Response)
            assert response.body == b'{"ok":true}'
