"""Guard that the WeChat entrypoint prompt advertises current Markdown support.

WeChat used to be plain-text only, so the system prompt told agents not to use
any Markdown. WeChat now renders most Markdown for agent replies, so the
entrypoint prompt must advertise what is supported (and the few things that
still are not) instead of the stale "plain text only" instruction.
"""

from datetime import datetime

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core import prompt as prompt_mod
from intentkit.core.prompt import build_entrypoint_prompt
from intentkit.models.agent import Agent, AgentVisibility
from intentkit.models.chat import AuthorType


def _wechat_agent() -> Agent:
    now = datetime.now()
    return Agent(
        id="agent-wechat",
        name="WeChat Agent",
        description="A test agent",
        model="gpt-4o",
        updated_at=now,
        created_at=now,
        owner="user_1",
        tools=None,
        system_prompt="You are a helper.",
        visibility=AgentVisibility.PRIVATE,
        public_info_updated_at=now,
    )


@pytest.mark.asyncio
async def test_wechat_entrypoint_prompt_advertises_markdown(monkeypatch):
    # Isolate from any deployment-configured WeChat system prompt so the
    # assertions only see the hardcoded capability description.
    monkeypatch.setattr(prompt_mod.config, "wechat_system_prompt", None)

    agent = _wechat_agent()
    context = AgentContext(
        agent_id=agent.id,
        get_agent=lambda: agent,
        chat_id="chat-1",
        entrypoint=AuthorType.WECHAT,
        is_own_team=True,
    )

    result = await build_entrypoint_prompt(agent, context)

    assert result is not None
    text = result.lower()

    # The stale "plain text only" claim is gone; WeChat now supports Markdown.
    assert "plain text" not in text
    assert "markdown" in text

    # Supported features are spelled out for the agent.
    for token in (
        "level-2 heading",
        "bold",
        "strikethrough",
        "horizontal rule",
        "ordered lists",
        "blockquote",
        "hyperlink",
        "inline code",
        "code block",
        "tables",
    ):
        assert token in text, f"missing supported feature: {token}"

    # The few unsupported features are still called out.
    for token in ("italics", "task lists", "images"):
        assert token in text, f"missing unsupported feature: {token}"

    # The UI-component restriction is retained — only the Markdown stance changed.
    assert "ui_ tools" in text
