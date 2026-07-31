"""Tests for system tools in intentkit/core/system_tools/."""

from datetime import datetime
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.tools.base import ToolException
from pydantic import ValidationError

from intentkit.abstracts.graph import AgentContext
from intentkit.clients.s3 import download_image_bytes
from intentkit.core.system_tools.call_agent import (
    MAX_CALL_DEPTH,
    CallAgentTool,
    render_attachments_awareness,
)
from intentkit.core.system_tools.create_activity import (
    CreateActivityInput,
    CreateActivityTool,
)
from intentkit.core.system_tools.current_time import CurrentTimeTool
from intentkit.core.system_tools.get_post import GetPostTool
from intentkit.core.system_tools.read_webpage import ReadWebpageCloudflareTool
from intentkit.core.system_tools.recent_activities import RecentActivitiesTool
from intentkit.core.system_tools.recent_posts import RecentPostsTool
from intentkit.core.system_tools.search_web import (
    WebSearchTool,
    _QuotaError,
)
from intentkit.core.system_tools.store_image import StoreImageTool
from intentkit.models.chat import (
    AuthorType,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
)


@pytest.fixture
def mock_runtime():
    """Fixture for mocked runtime context."""
    agent_id = "test_agent_123"
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = agent_id
    mock_context.call_depth = 0
    mock_context.chat_id = "chat_1"
    mock_context.user_id = "user_1"
    mock_context.team_id = "team_1"
    mock_context.payer = "team_1"
    mock_context.entrypoint = "web"
    mock_context.is_own_team = True
    mock_context.start_message_attachments = None
    mock_context.agent = MagicMock()
    mock_context.agent.sub_agents = None
    # The engine injects this on the real context; tools call it instead of
    # importing intentkit.core.engine.
    mock_context.execute_agent = AsyncMock(return_value=[])

    with patch("intentkit.core.system_tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


# ──────────────────────────────────────────────
# CurrentTimeTool
# ──────────────────────────────────────────────


def _extract_unix_timestamp(result: str) -> int:
    """Parse the ``Unix timestamp: <int>`` line from current_time output."""
    line = next(ln for ln in result.splitlines() if ln.startswith("Unix timestamp: "))
    return int(line.removeprefix("Unix timestamp: "))


@pytest.mark.asyncio
async def test_current_time_utc():
    """Default timezone returns current time with UTC."""
    tool = CurrentTimeTool()
    result = await tool._arun()
    assert result.startswith("Current time: ")
    assert "UTC" in result
    assert "Unix timestamp: " in result


@pytest.mark.asyncio
async def test_current_time_custom_timezone():
    """Custom timezone returns formatted time with that timezone."""
    tool = CurrentTimeTool()
    result = await tool._arun(timezone="Asia/Tokyo")
    assert result.startswith("Current time: ")
    assert "JST" in result or "Asia/Tokyo" in result


@pytest.mark.asyncio
async def test_current_time_includes_unix_timestamp():
    """Output includes a Unix timestamp close to the current time."""
    tool = CurrentTimeTool()
    before = int(datetime.now().timestamp())
    result = await tool._arun()
    after = int(datetime.now().timestamp())

    # The timestamp is timezone-independent and should fall within the window
    # spanning the call.
    assert before <= _extract_unix_timestamp(result) <= after


@pytest.mark.asyncio
async def test_current_time_unix_timestamp_timezone_independent():
    """The Unix timestamp does not depend on the requested timezone."""
    tool = CurrentTimeTool()

    utc_result = await tool._arun()
    tokyo_result = await tool._arun(timezone="Asia/Tokyo")

    # Both calls happen within a second, so timestamps should be within 2s.
    delta = abs(
        _extract_unix_timestamp(utc_result) - _extract_unix_timestamp(tokyo_result)
    )
    assert delta <= 2


@pytest.mark.asyncio
async def test_current_time_invalid_timezone():
    """Unknown timezone raises ToolException with suggestions."""
    tool = CurrentTimeTool()
    with pytest.raises(ToolException, match="Unknown timezone"):
        await tool._arun(timezone="Invalid/Zone")


# ──────────────────────────────────────────────
# CallAgentTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_agent_max_recursion(mock_runtime):
    """Exceeding MAX_CALL_DEPTH raises ToolException."""
    _, mock_context = mock_runtime
    mock_context.call_depth = MAX_CALL_DEPTH

    tool = CallAgentTool()
    with pytest.raises(ToolException, match="Maximum call_agent recursion depth"):
        await tool._arun(agent_id="other_agent", message="hello")


@pytest.mark.asyncio
async def test_call_agent_not_found(mock_runtime):
    """Agent not found raises ToolException."""
    tool = CallAgentTool()
    with patch(
        "intentkit.core.agent.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(ToolException, match="not found"):
            await tool._arun(agent_id="nonexistent", message="hello")


@pytest.mark.asyncio
async def test_call_agent_not_in_allowed(mock_runtime):
    """Agent not in sub_agents list raises ToolException."""
    _, mock_context = mock_runtime
    mock_context.agent.sub_agents = ["allowed_agent"]

    mock_resolved = MagicMock()
    mock_resolved.id = "other_id"
    mock_resolved.slug = "other_slug"

    tool = CallAgentTool()
    with patch(
        "intentkit.core.agent.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=mock_resolved),
    ):
        with pytest.raises(ToolException, match="not in the allowed sub-agents"):
            await tool._arun(agent_id="other_agent", message="hello")


@pytest.mark.asyncio
async def test_call_agent_success(mock_runtime):
    """Successful call returns (message, attachments)."""
    _, mock_context = mock_runtime
    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Hello from agent"
    mock_msg.attachments = []

    mock_context.execute_agent = AsyncMock(return_value=[mock_msg])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        result = await tool._arun(agent_id="target_id", message="hello")

    content, attachments = result
    assert content == "Hello from agent"
    assert isinstance(attachments, list)


@pytest.mark.asyncio
async def test_call_agent_success_with_attachments(mock_runtime):
    """Successful call appends an attachments awareness block to the text."""
    _, mock_context = mock_runtime
    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    attachments: list[ChatMessageAttachment] = [
        {
            "type": ChatMessageAttachmentType.IMAGE,
            "lead_text": "Here is the image",
            "url": "https://example.com/img.png",
            "json": None,
        },
        {
            "type": ChatMessageAttachmentType.CARD,
            "lead_text": None,
            "url": "https://example.com/card",
            "json": {
                "title": "Status",
                "description": "All good",
                "label": None,
                "image_url": None,
            },
        },
    ]

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Done."
    mock_msg.attachments = attachments

    mock_context.execute_agent = AsyncMock(return_value=[mock_msg])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        content, returned_attachments = await tool._arun(
            agent_id="target_id", message="hello"
        )

    assert content.startswith("Done.")
    assert "already been sent to the user" in content
    assert "do not resend" in content
    assert "[image]" in content
    assert "https://example.com/img.png" in content
    assert "[card]" in content
    assert 'title="Status"' in content
    assert returned_attachments == attachments


@pytest.mark.asyncio
async def test_call_agent_forwards_start_message_attachments(mock_runtime):
    """Delegation preserves inbound attachments from the current conversation."""
    _, mock_context = mock_runtime

    start_attachments: list[ChatMessageAttachment] = [
        {
            "type": ChatMessageAttachmentType.IMAGE,
            "lead_text": "User sent an image.",
            "url": "https://example.com/input.png",
            "json": None,
        }
    ]
    mock_context.start_message_attachments = start_attachments

    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Done"
    mock_msg.attachments = []

    mock_context.execute_agent = AsyncMock(return_value=[mock_msg])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        await tool._arun(agent_id="target_id", message="hello")

    assert mock_context.execute_agent.await_args is not None
    forwarded = mock_context.execute_agent.await_args.args[0]
    assert forwarded.attachments == start_attachments


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payer, team_id, expected",
    [
        # Payer resolved (payment enabled): bill the resolved payer, which can
        # differ from team_id on platform channels (payer = agent's team).
        ("payer_team", "ctx_team", "payer_team"),
        # No payer (payment disabled): fall back to the conversation's team_id.
        (None, "ctx_team", "ctx_team"),
    ],
)
async def test_call_agent_forwards_billing_payer(
    mock_runtime, payer, team_id, expected
):
    """The sub-agent inherits the caller's billing account via ``payer``.

    The cost is forwarded through the dedicated ``payer`` field, not ``team_id``,
    so delegation does not change the sub-agent's team access context. Prefer the
    resolved payer, falling back to team_id when payment is disabled.
    """
    _, mock_context = mock_runtime
    mock_context.payer = payer
    mock_context.team_id = team_id

    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Done"
    mock_msg.attachments = []

    mock_context.execute_agent = AsyncMock(return_value=[mock_msg])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        await tool._arun(agent_id="target_id", message="hello")

    assert mock_context.execute_agent.await_args is not None
    forwarded = mock_context.execute_agent.await_args.args[0]
    assert forwarded.payer == expected
    # team_id is intentionally left untouched so the sub-agent's access context
    # (is_own_team) is unaffected by delegation.
    assert forwarded.team_id is None


@pytest.mark.asyncio
async def test_call_agent_inherits_entrypoint(mock_runtime):
    """The sub-agent message carries the original entrypoint in thread_type."""
    _, mock_context = mock_runtime
    mock_context.entrypoint = AuthorType.TELEGRAM
    mock_context.call_depth = 2

    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Done"
    mock_msg.attachments = []

    mock_context.execute_agent = AsyncMock(return_value=[mock_msg])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        await tool._arun(agent_id="target_id", message="hello")

    assert mock_context.execute_agent.await_args is not None
    forwarded = mock_context.execute_agent.await_args.args[0]
    assert forwarded.author_type == AuthorType.INTERNAL.value
    assert forwarded.thread_type == AuthorType.TELEGRAM.value
    assert forwarded.call_depth == 3
    # The next hop's context rebuilds the same entrypoint from this message.
    assert forwarded.thread_entrypoint == AuthorType.TELEGRAM.value


def test_render_attachments_awareness_empty():
    """Empty attachment list yields an empty string."""
    assert render_attachments_awareness([]) == ""


def test_render_attachments_awareness_xmtp_uses_metadata_description():
    """XMTP attachments surface metadata.description instead of raw calldata."""
    attachments: list[ChatMessageAttachment] = [
        {
            "type": ChatMessageAttachmentType.XMTP,
            "lead_text": None,
            "url": None,
            "json": {
                "version": "1.0",
                "from": "0xabc",
                "chainId": "0x1",
                "calls": [
                    {
                        "to": "0xdef",
                        "value": "0x0",
                        "data": "0x" + "a" * 200,
                        "metadata": {
                            "description": "Send 10 USDC to 0xdef",
                            "transactionType": "erc20_transfer",
                        },
                    }
                ],
            },
        }
    ]
    rendered = render_attachments_awareness(attachments)

    assert "[xmtp]" in rendered
    assert 'description="Send 10 USDC to 0xdef"' in rendered
    assert "0x" + "a" * 200 not in rendered


def test_render_attachments_awareness_choice_and_link():
    """Choice and link types render with their type-specific fields."""
    attachments: list[ChatMessageAttachment] = [
        {
            "type": ChatMessageAttachmentType.LINK,
            "lead_text": "Docs",
            "url": "https://example.com",
            "json": None,
        },
        {
            "type": ChatMessageAttachmentType.CHOICE,
            "lead_text": "Pick one?",
            "url": None,
            "json": {
                "a": {"title": "Yes", "content": ""},
                "b": {"title": "No", "content": ""},
            },
        },
    ]
    rendered = render_attachments_awareness(attachments)

    assert "[link]" in rendered
    assert 'lead_text="Docs"' in rendered
    assert "url=https://example.com" in rendered
    assert "[choice]" in rendered
    assert 'lead_text="Pick one?"' in rendered
    assert 'a="Yes"' in rendered
    assert 'b="No"' in rendered


@pytest.mark.asyncio
async def test_call_agent_no_response(mock_runtime):
    """Empty results raises ToolException."""
    _, mock_context = mock_runtime
    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_context.execute_agent = AsyncMock(return_value=[])
    tool = CallAgentTool()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
    ):
        with pytest.raises(ToolException, match="No response received"):
            await tool._arun(agent_id="target_id", message="hello")


# ──────────────────────────────────────────────
# CreateActivityTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_activity_success(mock_runtime):
    """Successful activity creation returns success message with ID."""
    mock_activity = MagicMock()
    mock_activity.id = "activity_123"

    tool = CreateActivityTool()
    with patch(
        "intentkit.core.system_tools.create_activity.create_agent_activity",
        new=AsyncMock(return_value=mock_activity),
    ):
        result = await tool._arun(text="Hello world")

    assert "Activity created successfully with ID: activity_123" in result


@pytest.mark.asyncio
async def test_create_activity_refused_for_guests(mock_runtime):
    """team_only write tools must refuse when a guest runs a published agent."""
    _, mock_context = mock_runtime
    mock_context.is_own_team = False

    tool = CreateActivityTool()
    assert tool.team_only is True
    with pytest.raises(ToolException, match="own team"):
        await tool._arun(text="Hello world")


@pytest.mark.asyncio
async def test_create_activity_with_link(mock_runtime):
    """Activity with a link fetches link meta and includes in activity."""
    mock_activity = MagicMock()
    mock_activity.id = "activity_456"

    mock_meta = MagicMock()
    mock_meta.model_dump.return_value = {
        "title": "Example",
        "url": "https://example.com",
    }

    tool = CreateActivityTool()
    with (
        patch(
            "intentkit.core.system_tools.create_activity.create_agent_activity",
            new=AsyncMock(return_value=mock_activity),
        ),
        patch(
            "intentkit.core.system_tools.create_activity.fetch_link_meta",
            new=AsyncMock(return_value=mock_meta),
        ),
    ):
        result = await tool._arun(
            text="Check this out",
            link="https://example.com",
        )

    assert "Activity created successfully with ID: activity_456" in result


def test_create_activity_input_text_validation():
    """Text exceeding 280 bytes raises ValueError."""
    with pytest.raises(ValidationError):
        CreateActivityInput(text="a" * 281)


# ──────────────────────────────────────────────
# GetPostTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_post_success(mock_runtime):
    """Successful post retrieval returns formatted post with title and markdown."""
    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.title = "Test Post"
    mock_post.created_at = datetime(2024, 1, 1)
    mock_post.slug = "test-post"
    mock_post.excerpt = "An excerpt"
    mock_post.tags = ["tag1"]
    mock_post.cover = None
    mock_post.markdown = "# Content"

    tool = GetPostTool()
    with patch(
        "intentkit.core.system_tools.get_post.get_agent_post",
        new=AsyncMock(return_value=mock_post),
    ):
        result = await tool._arun(post_id="post_1")

    assert "Test Post" in result
    assert "# Content" in result
    assert "post_1" in result


@pytest.mark.asyncio
async def test_get_post_not_found(mock_runtime):
    """Post not found returns appropriate message."""
    tool = GetPostTool()
    with patch(
        "intentkit.core.system_tools.get_post.get_agent_post",
        new=AsyncMock(return_value=None),
    ):
        result = await tool._arun(post_id="nonexistent")

    assert "not found" in result


# ──────────────────────────────────────────────
# RecentActivitiesTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_activities_found(mock_runtime):
    """Returns formatted activities when activities exist."""
    mock_activity = MagicMock()
    mock_activity.id = "act_1"
    mock_activity.created_at = datetime(2024, 1, 1)
    mock_activity.text = "Did something"
    mock_activity.images = None
    mock_activity.video = None
    mock_activity.post_id = None

    tool = RecentActivitiesTool()
    with patch(
        "intentkit.core.system_tools.recent_activities.get_agent_activities",
        new=AsyncMock(return_value=[mock_activity]),
    ):
        result = await tool._arun()

    assert "1 recent activities" in result
    assert "Did something" in result


@pytest.mark.asyncio
async def test_recent_activities_empty(mock_runtime):
    """Returns no activities message when none found."""
    tool = RecentActivitiesTool()
    with patch(
        "intentkit.core.system_tools.recent_activities.get_agent_activities",
        new=AsyncMock(return_value=[]),
    ):
        result = await tool._arun()

    assert result == "No recent activities found."


# ──────────────────────────────────────────────
# RecentPostsTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_posts_found(mock_runtime):
    """Returns formatted posts when posts exist."""
    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.title = "My Post"
    mock_post.created_at = datetime(2024, 1, 1)
    mock_post.slug = "my-post"
    mock_post.excerpt = "Summary"
    mock_post.tags = ["tag1"]
    mock_post.cover = None

    tool = RecentPostsTool()
    with patch(
        "intentkit.core.system_tools.recent_posts.get_agent_posts",
        new=AsyncMock(return_value=[mock_post]),
    ):
        result = await tool._arun()

    assert "1 recent posts" in result
    assert "My Post" in result


@pytest.mark.asyncio
async def test_recent_posts_empty(mock_runtime):
    """Returns no posts message when none found."""
    tool = RecentPostsTool()
    with patch(
        "intentkit.core.system_tools.recent_posts.get_agent_posts",
        new=AsyncMock(return_value=[]),
    ):
        result = await tool._arun()

    assert result == "No recent posts found."


# ──────────────────────────────────────────────
# ReadWebpageCloudflareTool
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_webpage_cloudflare_missing_config():
    """Missing config raises ToolException."""
    tool = ReadWebpageCloudflareTool()
    with patch("intentkit.config.config.config") as mock_config:
        mock_config.cloudflare_account_id = None
        mock_config.cloudflare_api_token = None
        with pytest.raises(
            ToolException, match="Cloudflare Browser Rendering is not configured"
        ):
            await tool._arun("https://example.com")


@pytest.mark.asyncio
async def test_read_webpage_cloudflare_success():
    """Successful fetch and clean returns content."""
    tool = ReadWebpageCloudflareTool()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(
            tool, "_fetch_markdown", new=AsyncMock(return_value="raw markdown")
        ),
        patch.object(
            tool, "_clean_with_llm", new=AsyncMock(return_value="cleaned markdown")
        ),
    ):
        mock_config.cloudflare_account_id = "test_id"
        mock_config.cloudflare_api_token = "test_token"
        result = await tool._arun("https://example.com", tool_call_id="call_1")

    assert result == "cleaned markdown"


# ──────────────────────────────────────────────
# WebSearchTool
# ──────────────────────────────────────────────


class _FakeSearchResponse:
    """Minimal httpx-like response for web_search backend tests."""

    def __init__(
        self, status_code: int, json_data: dict | None = None, text: str = ""
    ) -> None:
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self) -> dict:
        return self._json


class _FakeAsyncClient:
    """Async-context-manager stub that returns a fixed response."""

    def __init__(self, response: _FakeSearchResponse) -> None:
        self._response = response

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, *args: object, **kwargs: object) -> _FakeSearchResponse:
        return self._response

    async def get(self, *args: object, **kwargs: object) -> _FakeSearchResponse:
        return self._response


def _set_search_keys(
    mock_config, *, tavily=None, jina=None, google=None, zai=None
) -> None:
    """Set the four web_search backend keys on a mocked config."""
    mock_config.tavily_api_key = tavily
    mock_config.jina_api_key = jina
    mock_config.google_api_key = google
    mock_config.zai_plan_api_key = zai


@pytest.mark.asyncio
async def test_web_search_no_backend_configured():
    """No keys at all raises a ToolException naming the env vars."""
    tool = WebSearchTool()
    with patch("intentkit.config.config.config") as mock_config:
        _set_search_keys(mock_config)
        with pytest.raises(ToolException, match="No web search backend"):
            await tool._arun("query")


@pytest.mark.asyncio
async def test_web_search_tavily_only_success():
    """Only Tavily configured → its result is returned."""
    tool = WebSearchTool()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(tool, "_in_cooldown", new=AsyncMock(return_value=False)),
        patch.object(
            tool, "_search_tavily", new=AsyncMock(return_value="tavily result")
        ),
    ):
        _set_search_keys(mock_config, tavily="k")
        result = await tool._arun("query")
    assert result == "tavily result"


@pytest.mark.asyncio
async def test_web_search_quota_falls_back_and_sets_cooldown():
    """Tavily out of quota → cooldown recorded and Jina used instead."""
    tool = WebSearchTool()
    set_cooldown = AsyncMock()
    with (
        patch("intentkit.config.config.config") as mock_config,
        # Pin the random order so Tavily is attempted first, deterministically.
        patch(
            "intentkit.core.system_tools.search_web.random.shuffle",
            lambda seq: None,
        ),
        patch.object(tool, "_in_cooldown", new=AsyncMock(return_value=False)),
        patch.object(tool, "_set_cooldown", new=set_cooldown),
        patch.object(
            tool, "_search_tavily", new=AsyncMock(side_effect=_QuotaError("429"))
        ),
        patch.object(tool, "_search_jina", new=AsyncMock(return_value="jina result")),
    ):
        _set_search_keys(mock_config, tavily="k", jina="k")
        result = await tool._arun("query")
    assert result == "jina result"
    set_cooldown.assert_awaited_once_with("tavily")


@pytest.mark.asyncio
async def test_web_search_falls_back_to_gemini_when_metered_exhausted():
    """Both Tavily and Jina out of quota → Gemini fallback is used."""
    tool = WebSearchTool()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(tool, "_in_cooldown", new=AsyncMock(return_value=False)),
        patch.object(tool, "_set_cooldown", new=AsyncMock()),
        patch.object(
            tool, "_search_tavily", new=AsyncMock(side_effect=_QuotaError("429"))
        ),
        patch.object(
            tool, "_search_jina", new=AsyncMock(side_effect=_QuotaError("402"))
        ),
        patch.object(
            tool, "_search_gemini", new=AsyncMock(return_value="gemini result")
        ),
    ):
        _set_search_keys(mock_config, tavily="k", jina="k", google="k", zai="k")
        result = await tool._arun("query")
    assert result == "gemini result"


@pytest.mark.asyncio
async def test_web_search_zai_is_last_resort():
    """Only Z.AI configured → it is used."""
    tool = WebSearchTool()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(tool, "_search_zai", new=AsyncMock(return_value="zai result")),
    ):
        _set_search_keys(mock_config, zai="k")
        result = await tool._arun("query")
    assert result == "zai result"


@pytest.mark.asyncio
async def test_web_search_skips_cooled_down_backend():
    """A cooled-down Tavily is skipped; Jina is used and Tavily never called."""
    tool = WebSearchTool()

    async def fake_cooldown(backend: str) -> bool:
        return backend == "tavily"

    tavily = AsyncMock(return_value="tavily result")
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(tool, "_in_cooldown", new=fake_cooldown),
        patch.object(tool, "_search_tavily", new=tavily),
        patch.object(tool, "_search_jina", new=AsyncMock(return_value="jina result")),
    ):
        _set_search_keys(mock_config, tavily="k", jina="k")
        result = await tool._arun("query")
    assert result == "jina result"
    tavily.assert_not_awaited()


@pytest.mark.asyncio
async def test_web_search_tavily_http_parsing():
    """_search_tavily parses results into the uniform format."""
    tool = WebSearchTool()
    response = _FakeSearchResponse(
        200,
        {"results": [{"title": "T", "url": "https://e.com", "content": "snippet"}]},
    )
    with patch(
        "intentkit.core.system_tools.search_web.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        result = await tool._search_tavily("k", "query", 5)
    assert "https://e.com" in result
    assert "snippet" in result
    assert "T" in result


@pytest.mark.asyncio
async def test_web_search_tavily_quota_status_raises_quota_error():
    """A 429 from Tavily becomes a _QuotaError."""
    tool = WebSearchTool()
    response = _FakeSearchResponse(429, text="rate limited")
    with patch(
        "intentkit.core.system_tools.search_web.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        with pytest.raises(_QuotaError):
            await tool._search_tavily("k", "query", 5)


@pytest.mark.asyncio
async def test_web_search_jina_http_parsing():
    """_search_jina parses the data list using description as the snippet."""
    tool = WebSearchTool()
    response = _FakeSearchResponse(
        200,
        {"data": [{"title": "J", "url": "https://j.com", "description": "desc"}]},
    )
    with patch(
        "intentkit.core.system_tools.search_web.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        result = await tool._search_jina("k", "query", 5)
    assert "https://j.com" in result
    assert "desc" in result


@pytest.mark.asyncio
async def test_web_search_jina_quota_status_raises_quota_error():
    """A 402 from Jina becomes a _QuotaError."""
    tool = WebSearchTool()
    response = _FakeSearchResponse(402, text="payment required")
    with patch(
        "intentkit.core.system_tools.search_web.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        with pytest.raises(_QuotaError):
            await tool._search_jina("k", "query", 5)


def test_web_search_format_results_empty():
    """No usable results yields a friendly message."""
    tool = WebSearchTool()
    assert "No results found" in tool._format_results("query", [])


# ──────────────────────────────────────────────
# StoreImageTool + download_image_bytes
# ──────────────────────────────────────────────

# 8-byte PNG signature is enough for filetype.guess to identify as image/png
_PNG_PAYLOAD = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_HTML_PAYLOAD = b"<!DOCTYPE html><html>not an image</html>"


class _FakeStreamResponse:
    """Minimal stand-in for an httpx streaming response."""

    def __init__(
        self,
        content: bytes,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
        chunk_size: int | None = None,
    ):
        self._content = content
        self._chunk_size = chunk_size
        self.headers = headers or {}
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://example.com/x")

    async def aread(self) -> bytes:
        return self._content

    async def aiter_bytes(self):
        if self._chunk_size is None:
            yield self._content
            return
        for start in range(0, len(self._content), self._chunk_size):
            yield self._content[start : start + self._chunk_size]


class _FakeStreamCM:
    def __init__(self, response: _FakeStreamResponse):
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *args: object) -> None:
        return None


def _patch_httpx_stream(
    monkeypatch,
    content: bytes,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
    chunk_size: int | None = None,
):
    """Patch httpx.AsyncClient.stream to return one fixed response for any URL."""
    response = _FakeStreamResponse(content, headers, status_code, chunk_size)

    def fake_stream(self, method, url, **kwargs):
        return _FakeStreamCM(response)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)


def _patch_httpx_stream_routes(monkeypatch, routes: dict[str, _FakeStreamResponse]):
    """Patch httpx.AsyncClient.stream to route by URL (for redirect chains)."""

    def fake_stream(self, method, url, **kwargs):
        url_str = str(url)
        response = routes.get(url_str)
        if response is None:
            raise AssertionError(f"unexpected stream URL in test: {url_str!r}")
        return _FakeStreamCM(response)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)


@pytest.mark.asyncio
async def test_download_image_bytes_returns_content_mime_ext(monkeypatch):
    """Valid image payload returns bytes + detected MIME + extension."""
    _patch_httpx_stream(monkeypatch, _PNG_PAYLOAD)
    content, mime, ext = await download_image_bytes("https://example.com/foo.png")
    assert content == _PNG_PAYLOAD
    assert mime == "image/png"
    assert ext == "png"


@pytest.mark.asyncio
async def test_download_image_bytes_rejects_svg_via_content_type(monkeypatch):
    """SVG must NOT be accepted via server Content-Type — XSS risk on CDN."""
    svg_payload = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    _patch_httpx_stream(
        monkeypatch, svg_payload, headers={"content-type": "image/svg+xml"}
    )
    with pytest.raises(ValueError, match="does not point to an image"):
        await download_image_bytes("https://example.com/foo.svg")


@pytest.mark.asyncio
async def test_download_image_bytes_rejects_non_image(monkeypatch):
    """Non-image payload with no image Content-Type raises ValueError."""
    _patch_httpx_stream(
        monkeypatch, _HTML_PAYLOAD, headers={"content-type": "text/html"}
    )
    with pytest.raises(ValueError, match="does not point to an image"):
        await download_image_bytes("https://example.com/foo.html")


@pytest.mark.asyncio
async def test_download_image_bytes_rejects_oversized_content_length(monkeypatch):
    """Content-Length header above the cap is rejected before streaming."""
    _patch_httpx_stream(
        monkeypatch, _PNG_PAYLOAD, headers={"content-length": str(50 * 1024 * 1024)}
    )
    with pytest.raises(ValueError, match="Response too large"):
        await download_image_bytes("https://example.com/big.png")


@pytest.mark.asyncio
async def test_download_image_bytes_ignores_malformed_content_length(monkeypatch):
    """A non-numeric Content-Length header is ignored; streaming check still wins."""
    _patch_httpx_stream(
        monkeypatch, _PNG_PAYLOAD, headers={"content-length": "chunked"}
    )
    content, mime, _ext = await download_image_bytes("https://example.com/foo.png")
    assert content == _PNG_PAYLOAD
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_download_image_bytes_per_chunk_cap(monkeypatch):
    """Per-chunk accumulator rejects payloads that exceed the cap mid-stream."""
    # Server lies (no Content-Length) and trickles >cap bytes in small chunks.
    big_payload = _PNG_PAYLOAD + b"\x00" * 4096
    _patch_httpx_stream(monkeypatch, big_payload, chunk_size=128)
    with pytest.raises(ValueError, match="Response too large"):
        await download_image_bytes("https://example.com/big.png", max_bytes=512)


@pytest.mark.asyncio
async def test_download_image_bytes_http_error_body_bounded(monkeypatch):
    """4xx response body is included in the error message but bounded against OOM."""
    # 5 MiB error body — must not be read in full into memory.
    huge_error = b'{"error": "signed URL expired"}' + b"X" * (5 * 1024 * 1024)
    _patch_httpx_stream(
        monkeypatch,
        huge_error,
        headers={"content-type": "application/json"},
        status_code=403,
        chunk_size=4096,
    )
    with pytest.raises(httpx.HTTPStatusError, match="signed URL expired"):
        await download_image_bytes("https://example.com/forbidden.png")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://127.0.0.1/foo.png",
        "http://localhost/foo.png",  # single-segment hostname
        "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
        "http://10.0.0.1/foo.png",
        "http://192.168.1.1/foo.png",
        "http://[::1]/foo.png",  # IPv6 loopback
        "http://redis/foo.png",  # docker service name
        "http://localhost./foo.png",  # FQDN-form bypass attempt
        "ftp://example.com/foo.png",  # disallowed scheme
    ],
)
async def test_download_image_bytes_rejects_internal_targets(blocked_url):
    """SSRF guard rejects internal/reserved targets before any HTTP call."""
    with pytest.raises(ValueError, match="Blocked|Only http"):
        await download_image_bytes(blocked_url)


@pytest.mark.asyncio
async def test_download_image_bytes_rejects_redirect_to_internal(monkeypatch):
    """A public URL that redirects to an internal address is rejected at the hop."""
    routes = {
        "https://evil.example.com/r": _FakeStreamResponse(
            b"", headers={"location": "http://169.254.169.254/"}, status_code=302
        ),
    }
    _patch_httpx_stream_routes(monkeypatch, routes)
    with pytest.raises(ValueError, match="Blocked internal"):
        await download_image_bytes("https://evil.example.com/r")


@pytest.mark.asyncio
async def test_download_image_bytes_follows_safe_redirect(monkeypatch):
    """A redirect to another public URL is followed and validated."""
    routes = {
        "https://short.example.com/abc": _FakeStreamResponse(
            b"",
            headers={"location": "https://cdn.example.com/foo.png"},
            status_code=302,
        ),
        "https://cdn.example.com/foo.png": _FakeStreamResponse(_PNG_PAYLOAD),
    }
    _patch_httpx_stream_routes(monkeypatch, routes)
    content, mime, _ext = await download_image_bytes("https://short.example.com/abc")
    assert content == _PNG_PAYLOAD
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_download_image_bytes_redirect_loop_rejected(monkeypatch):
    """Too many redirects raises ValueError rather than spinning indefinitely."""
    routes = {
        "https://a.example.com/": _FakeStreamResponse(
            b"", headers={"location": "https://b.example.com/"}, status_code=302
        ),
        "https://b.example.com/": _FakeStreamResponse(
            b"", headers={"location": "https://c.example.com/"}, status_code=302
        ),
        "https://c.example.com/": _FakeStreamResponse(
            b"", headers={"location": "https://d.example.com/"}, status_code=302
        ),
        "https://d.example.com/": _FakeStreamResponse(
            b"", headers={"location": "https://e.example.com/"}, status_code=302
        ),
    }
    _patch_httpx_stream_routes(monkeypatch, routes)
    with pytest.raises(ValueError, match="Too many redirects"):
        await download_image_bytes("https://a.example.com/")


@pytest.mark.asyncio
async def test_download_image_bytes_redirect_missing_location(monkeypatch):
    """A redirect status with no Location header raises HTTPStatusError."""
    _patch_httpx_stream(monkeypatch, b"", status_code=302)
    with pytest.raises(httpx.HTTPStatusError, match="missing Location"):
        await download_image_bytes("https://example.com/r")


@pytest.mark.asyncio
async def test_store_image_success(mock_runtime):
    """Successful download + upload returns the CDN URL."""
    tool = StoreImageTool()
    with (
        patch(
            "intentkit.core.system_tools.store_image.config.aws_s3_cdn_url",
            "https://cdn.example.com",
        ),
        patch(
            "intentkit.core.system_tools.store_image.download_image_bytes",
            new=AsyncMock(return_value=(_PNG_PAYLOAD, "image/png", "png")),
        ),
        patch(
            "intentkit.core.system_tools.store_image.store_image_bytes",
            new=AsyncMock(return_value="prod/test_agent_123/image/store_image/abc.png"),
        ),
        patch(
            "intentkit.core.system_tools.store_image.get_cdn_url",
            return_value="https://cdn.example.com/prod/test_agent_123/image/store_image/abc.png",
        ),
    ):
        result = await tool._arun("https://example.com/foo.png")

    assert result == (
        "https://cdn.example.com/prod/test_agent_123/image/store_image/abc.png"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cdn_config",
    ["https://cdn.example.com", "https://cdn.example.com/"],
)
async def test_store_image_internal_url_returned_as_is(mock_runtime, cdn_config):
    """URLs already on our CDN are returned unchanged without re-storing."""
    tool = StoreImageTool()
    download = AsyncMock()
    store = AsyncMock()
    with (
        patch(
            "intentkit.core.system_tools.store_image.config.aws_s3_cdn_url",
            cdn_config,
        ),
        patch(
            "intentkit.core.system_tools.store_image.download_image_bytes",
            new=download,
        ),
        patch(
            "intentkit.core.system_tools.store_image.store_image_bytes",
            new=store,
        ),
    ):
        url = "https://cdn.example.com/prod/agent/image/image_gemini_flash/x.png"
        assert await tool._arun(url) == url
    download.assert_not_awaited()
    store.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lookalike_url",
    [
        "https://cdn.example.com.evil.com/foo.png",
        "https://cdn.example.com@evil.com/foo.png",
    ],
)
async def test_store_image_lookalike_host_not_short_circuited(
    mock_runtime, lookalike_url
):
    """A lookalike host sharing the CDN prefix still goes through the store."""
    tool = StoreImageTool()
    with (
        patch(
            "intentkit.core.system_tools.store_image.config.aws_s3_cdn_url",
            "https://cdn.example.com",
        ),
        patch(
            "intentkit.core.system_tools.store_image.download_image_bytes",
            new=AsyncMock(return_value=(_PNG_PAYLOAD, "image/png", "png")),
        ),
        patch(
            "intentkit.core.system_tools.store_image.store_image_bytes",
            new=AsyncMock(return_value="prod/test_agent_123/image/store_image/abc.png"),
        ) as store,
        patch(
            "intentkit.core.system_tools.store_image.get_cdn_url",
            return_value="https://cdn.example.com/prod/test_agent_123/image/store_image/abc.png",
        ),
    ):
        result = await tool._arun(lookalike_url)

    store.assert_awaited_once()
    assert result == (
        "https://cdn.example.com/prod/test_agent_123/image/store_image/abc.png"
    )


@pytest.mark.asyncio
async def test_store_image_no_cdn_config_not_short_circuited(mock_runtime):
    """Without a configured CDN base, no URL is short-circuited."""
    tool = StoreImageTool()
    download = AsyncMock(side_effect=ValueError("URL does not point to an image"))
    with (
        patch(
            "intentkit.core.system_tools.store_image.config.aws_s3_cdn_url",
            None,
        ),
        patch(
            "intentkit.core.system_tools.store_image.download_image_bytes",
            new=download,
        ),
    ):
        with pytest.raises(ToolException, match="does not point to an image"):
            await tool._arun("/relative/path.png")
    download.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_image_rejects_non_image(mock_runtime):
    """ValueError from helper is surfaced as ToolException."""
    tool = StoreImageTool()
    with patch(
        "intentkit.core.system_tools.store_image.download_image_bytes",
        new=AsyncMock(side_effect=ValueError("URL does not point to an image")),
    ):
        with pytest.raises(ToolException, match="does not point to an image"):
            await tool._arun("https://example.com/foo.html")


@pytest.mark.asyncio
async def test_store_image_download_failure(mock_runtime):
    """httpx errors from helper surface as ToolException with a friendly prefix."""
    tool = StoreImageTool()
    with patch(
        "intentkit.core.system_tools.store_image.download_image_bytes",
        new=AsyncMock(side_effect=httpx.ConnectError("dns failure")),
    ):
        with pytest.raises(ToolException, match="Failed to download image"):
            await tool._arun("https://example.com/foo.png")


@pytest.mark.asyncio
async def test_store_image_s3_not_configured(mock_runtime):
    """When store_image_bytes returns empty (S3 unconfigured), raise ToolException."""
    tool = StoreImageTool()
    with (
        patch(
            "intentkit.core.system_tools.store_image.download_image_bytes",
            new=AsyncMock(return_value=(_PNG_PAYLOAD, "image/png", "png")),
        ),
        patch(
            "intentkit.core.system_tools.store_image.store_image_bytes",
            new=AsyncMock(return_value=""),
        ),
    ):
        with pytest.raises(ToolException, match="S3 storage is not configured"):
            await tool._arun("https://example.com/foo.png")
