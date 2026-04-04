"""Tests for system skills in intentkit/core/system_skills/."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.abstracts.graph import AgentContext
from intentkit.core.system_skills.call_agent import MAX_CALL_DEPTH, CallAgentSkill
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
from intentkit.models.chat import AuthorType


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
        patch.object(
            skill, "_fetch_markdown", new=AsyncMock(return_value="raw markdown")
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
    """Successful search returns formatted results."""
    skill = SearchWebZaiSkill()
    mock_results = [
        {"title": "Test", "url": "https://test.com", "snippet": "Test snippet"}
    ]
    with (
        patch("intentkit.config.config.config") as mock_config,
        patch.object(skill, "_search", new=AsyncMock(return_value=mock_results)),
        patch.object(skill, "_format_results", return_value="Formatted Results"),
    ):
        mock_config.zai_plan_api_key = "test_key"
        result = await skill._arun("test query")  # pyright: ignore[reportPrivateUsage]

    assert result == "Formatted Results"
