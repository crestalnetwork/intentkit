"""Tests for user account linking endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def google_identities():
    return [
        {
            "id": "google-id",
            "provider": "google",
            "identity_data": {"email": "user@gmail.com"},
        }
    ]


@pytest.fixture
def evm_identities():
    return [
        {
            "id": "web3-id",
            "provider": "web3",
            "identity_data": {"address": "0xabc", "chain": "ethereum"},
        }
    ]


@pytest.fixture
def both_identities(google_identities, evm_identities):
    return google_identities + evm_identities


class TestGetLinkedAccounts:
    @pytest.mark.asyncio
    async def test_returns_both_providers(self, both_identities):
        import json

        from app.team.user import get_linked_accounts

        with patch(
            "app.team.user.get_user_identities",
            new_callable=AsyncMock,
            return_value=both_identities,
        ):
            response = await get_linked_accounts(user_id="user-123")

        data = json.loads(bytes(response.body).decode("utf-8"))
        assert data["google"]["email"] == "user@gmail.com"
        assert data["google"]["linked"] is True
        assert data["evm"]["address"] == "0xabc"
        assert data["evm"]["linked"] is True

    @pytest.mark.asyncio
    async def test_returns_null_for_missing_provider(self, google_identities):
        import json

        from app.team.user import get_linked_accounts

        with patch(
            "app.team.user.get_user_identities",
            new_callable=AsyncMock,
            return_value=google_identities,
        ):
            response = await get_linked_accounts(user_id="user-123")

        data = json.loads(bytes(response.body).decode("utf-8"))
        assert data["google"] is not None
        assert data["evm"] is None


class TestMaybeUpgradeFirstTeam:
    @pytest.mark.asyncio
    async def test_upgrades_none_plan_to_free(self):
        from app.team.user import _maybe_upgrade_first_team

        mock_team = MagicMock()
        mock_team.plan = "none"

        with (
            patch(
                "app.team.user.User.get_first_owned_team_id",
                new_callable=AsyncMock,
                return_value="team-1",
            ),
            patch(
                "app.team.user.Team.get",
                new_callable=AsyncMock,
                return_value=mock_team,
            ),
            patch("app.team.user.get_session") as mock_get_session,
        ):
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            await _maybe_upgrade_first_team("user-123")

            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_upgrade_if_no_owned_team(self):
        from app.team.user import _maybe_upgrade_first_team

        with patch(
            "app.team.user.User.get_first_owned_team_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await _maybe_upgrade_first_team("user-123")

    @pytest.mark.asyncio
    async def test_no_upgrade_if_already_free(self):
        from app.team.user import _maybe_upgrade_first_team

        mock_team = MagicMock()
        mock_team.plan = "free"

        with (
            patch(
                "app.team.user.User.get_first_owned_team_id",
                new_callable=AsyncMock,
                return_value="team-1",
            ),
            patch(
                "app.team.user.Team.get",
                new_callable=AsyncMock,
                return_value=mock_team,
            ),
            patch("app.team.user.get_session") as mock_get_session,
        ):
            await _maybe_upgrade_first_team("user-123")
            mock_get_session.assert_not_called()
