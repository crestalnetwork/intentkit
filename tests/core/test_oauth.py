"""Tests for the HMAC-signed OAuth state used by the Slack/Lark install flows.

The state carries routing (team_id + channel) and a session binding (user_id), so
``complete_oauth`` can require that the caller is the same admin who started the
install — proven by the JWT matching the state's user_id — plus an admin role
check (confused-deputy defense).
"""

from unittest.mock import AsyncMock, patch

import pytest

from intentkit.core.team import oauth

MODULE = "intentkit.core.team.oauth"


def _with_secret(secret: str = "test-secret"):
    return patch.object(oauth.config, "oauth_state_secret", secret)


class TestOAuthState:
    def test_roundtrip(self):
        with _with_secret():
            state = oauth.sign_state("team123", "slack", "user-1")
            assert oauth.verify_state(state) == ("team123", "slack", "user-1")

    def test_tampered_state_rejected(self):
        with _with_secret():
            state = oauth.sign_state("team123", "slack", "user-1")
            bad = state[:-2] + ("aa" if not state.endswith("aa") else "bb")
            assert oauth.verify_state(bad) is None

    def test_wrong_secret_rejected(self):
        with _with_secret("secret-a"):
            state = oauth.sign_state("team123", "slack", "user-1")
        with _with_secret("secret-b"):
            assert oauth.verify_state(state) is None

    def test_expired_state_rejected(self):
        with _with_secret():
            with patch(f"{MODULE}.time.time", return_value=1000):
                state = oauth.sign_state("team123", "slack", "user-1")
            with patch(f"{MODULE}.time.time", return_value=1000 + 700):
                assert oauth.verify_state(state) is None

    def test_garbage_state_rejected(self):
        with _with_secret():
            assert oauth.verify_state("not-valid-base64!!") is None


class TestCompleteOAuth:
    """complete_oauth is the single authorization gate for both channels."""

    @pytest.mark.asyncio
    async def test_foreign_user_rejected(self):
        # State minted for user-attacker; a different admin can't redeem it,
        # even before any role check.
        with _with_secret():
            state = oauth.sign_state("team123", "slack", "user-attacker")
            with pytest.raises(oauth.OAuthStateError):
                await oauth.complete_oauth("user-victim", "the-code", state)

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self):
        with _with_secret():
            state = oauth.sign_state("team123", "slack", "user-1")
            with patch(f"{MODULE}.check_permission", AsyncMock(return_value=False)):
                with pytest.raises(oauth.OAuthForbiddenError):
                    await oauth.complete_oauth("user-1", "the-code", state)

    @pytest.mark.asyncio
    async def test_unknown_channel_rejected(self):
        with _with_secret():
            state = oauth.sign_state("team123", "discord", "user-1")
            with patch(f"{MODULE}.check_permission", AsyncMock(return_value=True)):
                with pytest.raises(oauth.OAuthStateError):
                    await oauth.complete_oauth("user-1", "the-code", state)

    @pytest.mark.asyncio
    async def test_admin_dispatches_to_channel(self):
        # A valid, admin-owned slack state runs the slack exchange.
        with _with_secret():
            state = oauth.sign_state("team123", "slack", "user-1")
            with (
                patch(f"{MODULE}.check_permission", AsyncMock(return_value=True)),
                patch(f"{MODULE}._complete_slack", AsyncMock()) as mock_slack,
            ):
                team_id, channel = await oauth.complete_oauth(
                    "user-1", "the-code", state
                )
            assert (team_id, channel) == ("team123", "slack")
            mock_slack.assert_awaited_once_with("team123", "user-1", "the-code")

    @pytest.mark.asyncio
    async def test_admin_dispatches_to_lark_with_user(self):
        # The Lark exchange forwards the installing admin's user_id so the
        # stored install is attributed to them (not the team).
        with _with_secret():
            state = oauth.sign_state("team123", "lark", "user-1")
            with (
                patch(f"{MODULE}.check_permission", AsyncMock(return_value=True)),
                patch(f"{MODULE}._complete_lark", AsyncMock()) as mock_lark,
            ):
                team_id, channel = await oauth.complete_oauth(
                    "user-1", "the-code", state
                )
            assert (team_id, channel) == ("team123", "lark")
            mock_lark.assert_awaited_once_with("team123", "user-1", "the-code")
