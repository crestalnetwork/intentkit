"""Tests for the interactive UI system tools and their per-request gating.

``ui_show_card`` / ``ui_ask_user`` are system tools bound to every agent.
They are ``interactive_only``: ``ToolBindingMiddleware`` drops them for
cron-triggered runs (entrypoint TRIGGER) and sub-agent calls, and keeps
them for every live channel (web, telegram, api, ...).
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.middleware import ToolBindingMiddleware
from intentkit.core.system_tools import current_time, ui_ask_user, ui_show_card
from intentkit.core.system_tools.ui_ask_user import UIAskUserTool
from intentkit.core.system_tools.ui_show_card import UIShowCardTool
from intentkit.models.chat import AuthorType, ChatMessageAttachmentType

# ──────────────────────────────────────────────
# Tool behavior
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_card_basic():
    """UIShowCardTool returns the CARD attachment structure."""
    tool = UIShowCardTool()

    content, attachments = await tool._arun(title="Test Card")

    assert content == "Card displayed successfully."
    assert len(attachments) == 1
    att = attachments[0]
    assert att["type"] == ChatMessageAttachmentType.CARD
    assert att["url"] is None
    assert att["lead_text"] is None
    json_data = att["json"]
    assert json_data is not None
    assert json_data["title"] == "Test Card"
    assert json_data["description"] is None
    assert json_data["label"] is None
    assert json_data["image_url"] is None


@pytest.mark.asyncio
async def test_show_card_with_lead_text_and_image():
    """UIShowCardTool passes through all optional fields."""
    tool = UIShowCardTool()

    _content, attachments = await tool._arun(
        title="Test Card",
        url="https://example.com",
        description="Description",
        label="Go",
        image_url="https://example.com/img.png",
        lead_text="Check this out:",
    )

    att = attachments[0]
    assert att["lead_text"] == "Check this out:"
    assert att["url"] == "https://example.com"
    json_data = att["json"]
    assert json_data is not None
    assert json_data["image_url"] == "https://example.com/img.png"
    assert json_data["description"] == "Description"
    assert json_data["label"] == "Go"


@pytest.mark.asyncio
async def test_ask_user_two_options():
    """UIAskUserTool returns the CHOICE attachment with two options."""
    tool = UIAskUserTool()

    content, attachments = await tool._arun(
        lead_text="Which do you prefer?",
        option_a_title="Option A",
        option_a_content="First option",
        option_b_title="Option B",
        option_b_content="Second option",
    )

    assert content == "Choice displayed successfully."
    assert len(attachments) == 1
    att = attachments[0]
    assert att["type"] == ChatMessageAttachmentType.CHOICE
    assert att["lead_text"] == "Which do you prefer?"
    assert att["url"] is None

    options = cast(dict[str, Any], att["json"])
    assert "a" in options
    assert "b" in options
    assert "c" not in options
    assert options["a"]["title"] == "Option A"
    assert options["b"]["content"] == "Second option"


@pytest.mark.asyncio
async def test_ask_user_three_options():
    """UIAskUserTool includes option C only when both title and content set."""
    tool = UIAskUserTool()

    _content, attachments = await tool._arun(
        lead_text="Pick one:",
        option_a_title="A",
        option_a_content="First",
        option_b_title="B",
        option_b_content="Second",
        option_c_title="C",
        option_c_content="Third",
    )

    options = cast(dict[str, Any], attachments[0]["json"])
    assert options is not None
    assert "c" in options
    assert options["c"]["title"] == "C"
    assert options["c"]["content"] == "Third"


def test_tool_metadata():
    """Names, response format, and the interactive_only marker."""
    assert ui_show_card.name == "ui_show_card"
    assert ui_show_card.response_format == "content_and_artifact"
    assert ui_show_card.interactive_only is True
    assert ui_show_card.team_only is False

    assert ui_ask_user.name == "ui_ask_user"
    assert ui_ask_user.response_format == "content_and_artifact"
    assert ui_ask_user.interactive_only is True
    assert ui_ask_user.return_direct is True


# ──────────────────────────────────────────────
# ToolBindingMiddleware gating
# ──────────────────────────────────────────────


def _make_context(entrypoint: AuthorType, call_depth: int = 0) -> AgentContext:
    return AgentContext(
        agent_id="agent-1",
        get_agent=lambda: MagicMock(),
        chat_id="chat-1",
        user_id="user-1",
        entrypoint=entrypoint,
        is_own_team=True,
        call_depth=call_depth,
    )


class _FakeRequest:
    """Minimal stand-in for ModelRequest: runtime.context plus override()."""

    def __init__(self, context: AgentContext) -> None:
        self.runtime = SimpleNamespace(context=context)
        self.overridden: dict[str, Any] = {}

    def override(self, **kwargs: Any) -> "_FakeRequest":
        self.overridden.update(kwargs)
        return self


async def _bound_tool_names(context: AgentContext) -> set[str]:
    llm_model = MagicMock()
    llm_model.create_instance = AsyncMock(return_value=MagicMock())
    middleware = ToolBindingMiddleware(
        llm_model, [current_time, ui_show_card, ui_ask_user]
    )
    request = _FakeRequest(context)
    handler = AsyncMock(return_value="response")
    await middleware.awrap_model_call(cast(Any, request), handler)
    handler.assert_awaited_once()
    return {t.name for t in request.overridden["tools"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entrypoint",
    [
        AuthorType.WEB,
        AuthorType.TELEGRAM,
        AuthorType.API,
        AuthorType.WECHAT,
        AuthorType.LARK,
        AuthorType.SLACK,
        AuthorType.DISCORD,
        AuthorType.TWITTER,
        AuthorType.XMTP,
        AuthorType.X402,
    ],
)
async def test_ui_tools_bound_for_live_channels(entrypoint: AuthorType):
    """Every live entry channel gets the UI tools."""
    names = await _bound_tool_names(_make_context(entrypoint))
    assert "ui_show_card" in names
    assert "ui_ask_user" in names


@pytest.mark.asyncio
async def test_ui_tools_dropped_for_cron_trigger():
    """Cron/autonomous runs (entrypoint TRIGGER) never see the UI tools."""
    names = await _bound_tool_names(_make_context(AuthorType.TRIGGER))
    assert "ui_show_card" not in names
    assert "ui_ask_user" not in names
    assert "current_time" in names


@pytest.mark.asyncio
async def test_ui_tools_dropped_for_subagent():
    """Sub-agent runs keep the inherited entrypoint but still lose UI tools."""
    names = await _bound_tool_names(_make_context(AuthorType.TELEGRAM, call_depth=1))
    assert "ui_show_card" not in names
    assert "ui_ask_user" not in names
    assert "current_time" in names
