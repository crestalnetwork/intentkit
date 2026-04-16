"""Tests for system skills in intentkit/core/system_skills/."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.abstracts.graph import AgentContext
from intentkit.core.system_skills.call_agent import (
    MAX_CALL_DEPTH,
    CallAgentSkill,
    render_attachments_awareness,
)
from intentkit.core.system_skills.create_activity import (
    CreateActivityInput,
    CreateActivitySkill,
)
from intentkit.core.system_skills.current_time import CurrentTimeSkill
from intentkit.core.system_skills.get_post import GetPostSkill
from intentkit.core.system_skills.read_webpage import (
    ReadWebpageCloudflareSkill,
    ReadWebpageZaiSkill,
)
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill
from intentkit.core.system_skills.recent_posts import RecentPostsSkill
from intentkit.core.system_skills.search_web import SearchWebZaiSkill
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
    mock_context.entrypoint = "web"
    mock_context.start_message_attachments = None
    mock_context.agent = MagicMock()
    mock_context.agent.sub_agents = None

    with patch("intentkit.core.system_skills.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


# ──────────────────────────────────────────────
# CurrentTimeSkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_time_utc():
    """Default timezone returns current time with UTC."""
    skill = CurrentTimeSkill()
    result = await skill._arun()  # pyright: ignore[reportPrivateUsage]
    assert result.startswith("Current time: ")
    assert "UTC" in result


@pytest.mark.asyncio
async def test_current_time_custom_timezone():
    """Custom timezone returns formatted time with that timezone."""
    skill = CurrentTimeSkill()
    result = await skill._arun(timezone="Asia/Tokyo")  # pyright: ignore[reportPrivateUsage]
    assert result.startswith("Current time: ")
    assert "JST" in result or "Asia/Tokyo" in result


@pytest.mark.asyncio
async def test_current_time_invalid_timezone():
    """Unknown timezone raises ToolException with suggestions."""
    skill = CurrentTimeSkill()
    with pytest.raises(ToolException, match="Unknown timezone"):
        await skill._arun(timezone="Invalid/Zone")  # pyright: ignore[reportPrivateUsage]


# ──────────────────────────────────────────────
# CallAgentSkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_agent_max_recursion(mock_runtime):
    """Exceeding MAX_CALL_DEPTH raises ToolException."""
    _, mock_context = mock_runtime
    mock_context.call_depth = MAX_CALL_DEPTH

    skill = CallAgentSkill()
    with pytest.raises(ToolException, match="Maximum call_agent recursion depth"):
        await skill._arun(agent_id="other_agent", message="hello")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_call_agent_not_found(mock_runtime):
    """Agent not found raises ToolException."""
    skill = CallAgentSkill()
    with patch(
        "intentkit.core.agent.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(ToolException, match="not found"):
            await skill._arun(agent_id="nonexistent", message="hello")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_call_agent_not_in_allowed(mock_runtime):
    """Agent not in sub_agents list raises ToolException."""
    _, mock_context = mock_runtime
    mock_context.agent.sub_agents = ["allowed_agent"]

    mock_resolved = MagicMock()
    mock_resolved.id = "other_id"
    mock_resolved.slug = "other_slug"

    skill = CallAgentSkill()
    with patch(
        "intentkit.core.agent.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=mock_resolved),
    ):
        with pytest.raises(ToolException, match="not in the allowed sub-agents"):
            await skill._arun(agent_id="other_agent", message="hello")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_call_agent_success(mock_runtime):
    """Successful call returns (message, attachments)."""
    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    mock_msg = MagicMock()
    mock_msg.author_type = AuthorType.AGENT
    mock_msg.message = "Hello from agent"
    mock_msg.attachments = []

    skill = CallAgentSkill()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
        patch(
            "intentkit.core.engine.execute_agent",
            new=AsyncMock(return_value=[mock_msg]),
        ),
    ):
        result = await skill._arun(agent_id="target_id", message="hello")  # pyright: ignore[reportPrivateUsage]

    content, attachments = result
    assert content == "Hello from agent"
    assert isinstance(attachments, list)


@pytest.mark.asyncio
async def test_call_agent_success_with_attachments(mock_runtime):
    """Successful call appends an attachments awareness block to the text."""
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

    skill = CallAgentSkill()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
        patch(
            "intentkit.core.engine.execute_agent",
            new=AsyncMock(return_value=[mock_msg]),
        ),
    ):
        content, returned_attachments = await skill._arun(  # pyright: ignore[reportPrivateUsage]
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

    skill = CallAgentSkill()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
        patch(
            "intentkit.core.engine.execute_agent",
            new=AsyncMock(return_value=[mock_msg]),
        ) as mock_execute_agent,
    ):
        await skill._arun(agent_id="target_id", message="hello")  # pyright: ignore[reportPrivateUsage]

    assert mock_execute_agent.await_args is not None
    forwarded = mock_execute_agent.await_args.args[0]
    assert forwarded.attachments == start_attachments


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
    mock_resolved = MagicMock()
    mock_resolved.id = "target_id"
    mock_resolved.slug = "target_slug"

    skill = CallAgentSkill()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=mock_resolved),
        ),
        patch(
            "intentkit.core.engine.execute_agent",
            new=AsyncMock(return_value=[]),
        ),
    ):
        with pytest.raises(ToolException, match="No response received"):
            await skill._arun(agent_id="target_id", message="hello")  # pyright: ignore[reportPrivateUsage]


# ──────────────────────────────────────────────
# CreateActivitySkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_activity_success(mock_runtime):
    """Successful activity creation returns success message with ID."""
    mock_agent = MagicMock()
    mock_agent.name = "Test Agent"
    mock_agent.picture = "https://example.com/avatar.png"

    mock_activity = MagicMock()
    mock_activity.id = "activity_123"

    skill = CreateActivitySkill()
    with (
        patch(
            "intentkit.core.system_skills.create_activity.get_agent",
            new=AsyncMock(return_value=mock_agent),
        ),
        patch(
            "intentkit.core.system_skills.create_activity.create_agent_activity",
            new=AsyncMock(return_value=mock_activity),
        ),
    ):
        result = await skill._arun(text="Hello world")  # pyright: ignore[reportPrivateUsage]

    assert "Activity created successfully with ID: activity_123" in result


@pytest.mark.asyncio
async def test_create_activity_with_link(mock_runtime):
    """Activity with a link fetches link meta and includes in activity."""
    mock_agent = MagicMock()
    mock_agent.name = "Test Agent"
    mock_agent.picture = "https://example.com/avatar.png"

    mock_activity = MagicMock()
    mock_activity.id = "activity_456"

    mock_meta = MagicMock()
    mock_meta.model_dump.return_value = {
        "title": "Example",
        "url": "https://example.com",
    }

    skill = CreateActivitySkill()
    with (
        patch(
            "intentkit.core.system_skills.create_activity.get_agent",
            new=AsyncMock(return_value=mock_agent),
        ),
        patch(
            "intentkit.core.system_skills.create_activity.create_agent_activity",
            new=AsyncMock(return_value=mock_activity),
        ),
        patch(
            "intentkit.core.system_skills.create_activity.fetch_link_meta",
            new=AsyncMock(return_value=mock_meta),
        ),
    ):
        result = await skill._arun(  # pyright: ignore[reportPrivateUsage]
            text="Check this out",
            link="https://example.com",
        )

    assert "Activity created successfully with ID: activity_456" in result


def test_create_activity_input_text_validation():
    """Text exceeding 280 bytes raises ValueError."""
    with pytest.raises(Exception):
        CreateActivityInput(text="a" * 281)


# ──────────────────────────────────────────────
# GetPostSkill
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

    skill = GetPostSkill()
    with patch(
        "intentkit.core.system_skills.get_post.get_agent_post",
        new=AsyncMock(return_value=mock_post),
    ):
        result = await skill._arun(post_id="post_1")  # pyright: ignore[reportPrivateUsage]

    assert "Test Post" in result
    assert "# Content" in result
    assert "post_1" in result


@pytest.mark.asyncio
async def test_get_post_not_found(mock_runtime):
    """Post not found returns appropriate message."""
    skill = GetPostSkill()
    with patch(
        "intentkit.core.system_skills.get_post.get_agent_post",
        new=AsyncMock(return_value=None),
    ):
        result = await skill._arun(post_id="nonexistent")  # pyright: ignore[reportPrivateUsage]

    assert "not found" in result


# ──────────────────────────────────────────────
# RecentActivitiesSkill
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

    skill = RecentActivitiesSkill()
    with patch(
        "intentkit.core.system_skills.recent_activities.get_agent_activities",
        new=AsyncMock(return_value=[mock_activity]),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "1 recent activities" in result
    assert "Did something" in result


@pytest.mark.asyncio
async def test_recent_activities_empty(mock_runtime):
    """Returns no activities message when none found."""
    skill = RecentActivitiesSkill()
    with patch(
        "intentkit.core.system_skills.recent_activities.get_agent_activities",
        new=AsyncMock(return_value=[]),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert result == "No recent activities found."


# ──────────────────────────────────────────────
# RecentPostsSkill
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

    skill = RecentPostsSkill()
    with patch(
        "intentkit.core.system_skills.recent_posts.get_agent_posts",
        new=AsyncMock(return_value=[mock_post]),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "1 recent posts" in result
    assert "My Post" in result


@pytest.mark.asyncio
async def test_recent_posts_empty(mock_runtime):
    """Returns no posts message when none found."""
    skill = RecentPostsSkill()
    with patch(
        "intentkit.core.system_skills.recent_posts.get_agent_posts",
        new=AsyncMock(return_value=[]),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert result == "No recent posts found."


# ──────────────────────────────────────────────
# ReadWebpageCloudflareSkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_webpage_cloudflare_missing_config():
    """Missing config raises ToolException."""
    skill = ReadWebpageCloudflareSkill()
    with patch("intentkit.config.config.config") as mock_config:
        mock_config.cloudflare_account_id = None
        mock_config.cloudflare_api_token = None
        with pytest.raises(
            ToolException, match="Cloudflare Browser Rendering is not configured"
        ):
            await skill._arun("https://example.com")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_read_webpage_cloudflare_success():
    """Successful fetch and clean returns content."""
    skill = ReadWebpageCloudflareSkill()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(
            skill, "_fetch_markdown", new=AsyncMock(return_value="raw markdown")
        ),
        patch.object(
            skill, "_clean_with_llm", new=AsyncMock(return_value="cleaned markdown")
        ),
    ):
        mock_config.cloudflare_account_id = "test_id"
        mock_config.cloudflare_api_token = "test_token"
        result = await skill._arun("https://example.com", tool_call_id="call_1")  # pyright: ignore[reportPrivateUsage]

    assert result == "cleaned markdown"


# ──────────────────────────────────────────────
# ReadWebpageZaiSkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_webpage_zai_missing_config():
    """Missing config raises ToolException."""
    skill = ReadWebpageZaiSkill()
    with patch("intentkit.config.config.config") as mock_config:
        mock_config.zai_plan_api_key = None
        with pytest.raises(ToolException, match="Z.AI Plan API is not configured"):
            await skill._arun("https://example.com")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_read_webpage_zai_success():
    """Successful fetch returns content."""
    skill = ReadWebpageZaiSkill()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch(
            "intentkit.core.system_skills.read_webpage.call_mcp_tool",
            new=AsyncMock(return_value="raw markdown"),
        ),
    ):
        mock_config.zai_plan_api_key = "test_key"
        result = await skill._arun("https://example.com")  # pyright: ignore[reportPrivateUsage]

    assert result == "raw markdown"


# ──────────────────────────────────────────────
# SearchWebZaiSkill
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_web_zai_missing_config():
    """Missing config raises ToolException."""
    skill = SearchWebZaiSkill()
    with patch("intentkit.config.config.config") as mock_config:
        mock_config.zai_plan_api_key = None
        with pytest.raises(ToolException, match="Z.AI Plan API is not configured"):
            await skill._arun("test query")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_search_web_zai_success():
    """Successful search returns MCP tool result."""
    skill = SearchWebZaiSkill()
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch(
            "intentkit.core.system_skills.search_web.call_mcp_tool",
            new=AsyncMock(return_value="MCP search results"),
        ),
    ):
        mock_config.zai_plan_api_key = "test_key"
        result = await skill._arun("test query")  # pyright: ignore[reportPrivateUsage]

    assert result == "MCP search results"
