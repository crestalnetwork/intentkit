"""Tests for team plan initialization logic."""

from unittest.mock import AsyncMock, patch

import pytest


class TestDetermineInitialPlan:
    @pytest.mark.asyncio
    async def test_google_signup_first_team_gets_free(self):
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "g-id",
                        "provider": "google",
                        "identity_data": {"email": "user@gmail.com"},
                    }
                ],
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.FREE

    @pytest.mark.asyncio
    async def test_evm_signup_rich_wallet_gets_free(self):
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "w-id",
                        "provider": "web3",
                        "identity_data": {"address": "0xrich", "chain": "ethereum"},
                    }
                ],
            ),
            patch(
                "app.team.team.get_wallet_net_worth",
                new_callable=AsyncMock,
                return_value=100.0,
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.FREE

    @pytest.mark.asyncio
    async def test_evm_signup_poor_wallet_gets_none(self):
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "w-id",
                        "provider": "web3",
                        "identity_data": {"address": "0xpoor", "chain": "ethereum"},
                    }
                ],
            ),
            patch(
                "app.team.team.get_wallet_net_worth",
                new_callable=AsyncMock,
                return_value=5.0,
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.NONE

    @pytest.mark.asyncio
    async def test_second_team_always_none(self):
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with patch(
            "app.team.team.User.count_owned_teams",
            new_callable=AsyncMock,
            return_value=2,
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.NONE

    @pytest.mark.asyncio
    async def test_no_identities_gets_none(self):
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.NONE

    @pytest.mark.asyncio
    async def test_evm_exactly_20_gets_none(self):
        """Wallet must be > $20, not >= $20."""
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "w-id",
                        "provider": "web3",
                        "identity_data": {"address": "0xborder", "chain": "ethereum"},
                    }
                ],
            ),
            patch(
                "app.team.team.get_wallet_net_worth",
                new_callable=AsyncMock,
                return_value=20.0,
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.NONE

    @pytest.mark.asyncio
    async def test_google_takes_priority_over_evm(self):
        """If user has both Google and EVM, Google gives free immediately."""
        from intentkit.models.team import TeamPlan

        from app.team.team import _determine_initial_plan

        with (
            patch(
                "app.team.team.User.count_owned_teams",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.team.team.get_user_identities",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "g-id",
                        "provider": "google",
                        "identity_data": {"email": "user@gmail.com"},
                    },
                    {
                        "id": "w-id",
                        "provider": "web3",
                        "identity_data": {"address": "0xpoor", "chain": "ethereum"},
                    },
                ],
            ),
        ):
            plan = await _determine_initial_plan("user-123")

        assert plan == TeamPlan.FREE
