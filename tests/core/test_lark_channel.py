"""Tests for the Lark/Feishu channel wiring across the Python backend and a
drift guard against the Go integration's channel-type constant."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from intentkit.core.team.channel import (
    CHANNEL_CHAT_ID_PREFIXES,
    build_channel_chat_id,
)
from intentkit.models.chat import AuthorType
from intentkit.models.team_channel import LarkChannelConfig
from intentkit.models.user import User, UserUpdate

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_HANDLER = REPO_ROOT / "integrations" / "lark" / "bot" / "handler.go"


class TestLarkChannelConfig:
    def test_accepts_tenant_key(self):
        cfg = LarkChannelConfig.model_validate({"tenant_key": "tk_1"})
        assert cfg.tenant_key == "tk_1"

    def test_requires_tenant_key(self):
        with pytest.raises(ValidationError):
            LarkChannelConfig.model_validate({})


class TestLarkChatId:
    def test_prefix_registered(self):
        assert CHANNEL_CHAT_ID_PREFIXES["lark"] == "lk_team"

    def test_build_channel_chat_id(self):
        assert (
            build_channel_chat_id("lark", "team1", "oc_abc") == "lk_team:team1:oc_abc"
        )


class TestLarkResolution:
    def test_author_type_value(self):
        assert AuthorType.LARK.value == "lark"

    def test_channel_config_entry(self):
        # Imported lazily so a heavy core.api import doesn't burden unrelated tests.
        from intentkit.core.api import _CHANNEL_CONFIG

        assert "lark" in _CHANNEL_CONFIG
        lookup, bind_field, author_type, prefix = _CHANNEL_CONFIG["lark"]
        assert lookup == "get_by_lark_id"
        assert bind_field == "lark_id"
        assert author_type == AuthorType.LARK
        # The prefix in the dispatch table must match the chat-id builder, or
        # inbound and pushed messages would land in different chat threads.
        assert prefix == CHANNEL_CHAT_ID_PREFIXES["lark"]

    def test_user_lookup_and_bind_field_exist(self):
        # _resolve_lead does getattr(User, lookup)(...) and
        # UserUpdate.model_validate({bind_field: ...}); both must resolve.
        assert callable(User.get_by_lark_id)
        assert "lark_id" in UserUpdate.model_fields


def test_go_channel_type_matches_python() -> None:
    """The Go integration hard-codes channel_type="lark" in the payload it
    sends to /core/lead/stream; it must match the _CHANNEL_CONFIG key or every
    inbound message would be 400-rejected as an unsupported channel."""
    from intentkit.core.api import _CHANNEL_CONFIG

    src = GO_HANDLER.read_text()
    for key in _CHANNEL_CONFIG:
        if key == "lark":
            assert 'channelType = "lark"' in src, (
                "Go handler.go channelType const drifted from Python "
                "_CHANNEL_CONFIG key 'lark'"
            )
