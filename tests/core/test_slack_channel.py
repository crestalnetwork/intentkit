"""Tests for the Slack channel wiring across the Python backend and a drift
guard against the Go integration's channel-type constant."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from intentkit.core.team.channel import (
    CHANNEL_CHAT_ID_PREFIXES,
    build_channel_chat_id,
)
from intentkit.models.chat import AuthorType
from intentkit.models.team_channel import SlackChannelConfig
from intentkit.models.user import User, UserUpdate

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_HANDLER = REPO_ROOT / "integrations" / "slack" / "bot" / "handler.go"


class TestSlackChannelConfig:
    def test_accepts_install_config(self):
        cfg = SlackChannelConfig.model_validate(
            {"workspace_id": "T1", "bot_token": "xoxb-1"}
        )
        assert cfg.workspace_id == "T1"
        assert cfg.bot_token == "xoxb-1"

    def test_requires_workspace_id(self):
        with pytest.raises(ValidationError):
            SlackChannelConfig.model_validate({"bot_token": "xoxb-1"})

    def test_requires_bot_token(self):
        with pytest.raises(ValidationError):
            SlackChannelConfig.model_validate({"workspace_id": "T1"})


class TestSlackChatId:
    def test_prefix_registered(self):
        assert CHANNEL_CHAT_ID_PREFIXES["slack"] == "sl_team"

    def test_build_channel_chat_id(self):
        assert build_channel_chat_id("slack", "team1", "C0ABC") == "sl_team:team1:C0ABC"


class TestSlackResolution:
    def test_author_type_value(self):
        assert AuthorType.SLACK.value == "slack"

    def test_channel_config_entry(self):
        # Imported lazily so a heavy core.api import doesn't burden unrelated tests.
        from intentkit.core.api import _CHANNEL_CONFIG

        assert "slack" in _CHANNEL_CONFIG
        lookup, bind_field, author_type, prefix = _CHANNEL_CONFIG["slack"]
        assert lookup == "get_by_slack_id"
        assert bind_field == "slack_id"
        assert author_type == AuthorType.SLACK
        # The prefix in the dispatch table must match the chat-id builder, or
        # inbound and pushed messages would land in different chat threads.
        assert prefix == CHANNEL_CHAT_ID_PREFIXES["slack"]

    def test_user_lookup_and_bind_field_exist(self):
        # _resolve_lead does getattr(User, lookup)(...) and
        # UserUpdate.model_validate({bind_field: ...}); both must resolve.
        assert callable(User.get_by_slack_id)
        assert "slack_id" in UserUpdate.model_fields


def test_go_channel_type_matches_python() -> None:
    """The Go integration hard-codes channel_type="slack" in the payload it
    sends to /core/lead/stream; it must match the _CHANNEL_CONFIG key or every
    inbound message would be 400-rejected as an unsupported channel."""
    from intentkit.core.api import _CHANNEL_CONFIG

    src = GO_HANDLER.read_text()
    for key in _CHANNEL_CONFIG:
        if key == "slack":
            assert 'channelType = "slack"' in src, (
                "Go handler.go channelType const drifted from Python "
                "_CHANNEL_CONFIG key 'slack'"
            )
