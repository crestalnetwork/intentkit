"""Tests for lead sub-agents: self-updater, content-manager, and user-manager."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext


@pytest.fixture
def mock_lead_runtime():
    """Fixture for mocked runtime context with team_id."""
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = "team-test-team"
    mock_context.team_id = "test-team"
    mock_context.chat_id = "chat_1"
    mock_context.user_id = "user_1"

    with patch("intentkit.tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


# ──────────────────────────────────────────────
# LeadGetSelfInfo
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_self_info_defaults(mock_lead_runtime):
    """Returns default values when no persisted config exists."""
    from intentkit.core.lead.tools.get_self_info import LeadGetSelfInfo

    tool = LeadGetSelfInfo()
    with (
        patch(
            "intentkit.core.lead.tools.get_self_info.Team.get_lead_agent_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "intentkit.core.lead.tools.get_self_info.Memory.get",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await tool._arun()

    from intentkit.core.lead.constants import LEAD_DEFAULT_PERSONALITY

    assert result.name == "Team Lead"
    assert result.avatar is None
    assert result.personality == LEAD_DEFAULT_PERSONALITY
    assert result.memory is None


@pytest.mark.asyncio
async def test_get_self_info_with_config(mock_lead_runtime):
    """Returns persisted config values when they exist."""
    from intentkit.core.lead.tools.get_self_info import LeadGetSelfInfo

    mock_memory = MagicMock()
    mock_memory.content = "I remember things"

    tool = LeadGetSelfInfo()
    with (
        patch(
            "intentkit.core.lead.tools.get_self_info.Team.get_lead_agent_config",
            new=AsyncMock(
                return_value={
                    "name": "Custom Lead",
                    "avatar": "https://example.com/avatar.png",
                    "personality": "Friendly and professional",
                }
            ),
        ),
        patch(
            "intentkit.core.lead.tools.get_self_info.Memory.get",
            new=AsyncMock(return_value=mock_memory),
        ),
    ):
        result = await tool._arun()

    assert result.name == "Custom Lead"
    assert result.avatar == "https://example.com/avatar.png"
    assert result.personality == "Friendly and professional"
    assert result.memory == "I remember things"


# ──────────────────────────────────────────────
# LeadUpdateSelf
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_self_name(mock_lead_runtime):
    """Updates name and invalidates cache."""
    from intentkit.core.lead.tools.update_self import LeadUpdateSelf

    tool = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.tools.update_self.Team.update_lead_agent_config",
            new=AsyncMock(return_value={"name": "New Name"}),
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        result = await tool._arun(name="New Name")

    assert "name" in result.updated_fields
    assert result.message == "Lead agent updated: name."
    mock_invalidate.assert_called_once_with("test-team")


@pytest.mark.asyncio
async def test_update_self_multiple_fields(mock_lead_runtime):
    """Updates multiple fields at once."""
    from intentkit.core.lead.tools.update_self import LeadUpdateSelf

    tool = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.tools.update_self.Team.update_lead_agent_config",
            new=AsyncMock(return_value={}),
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache"),
    ):
        result = await tool._arun(
            name="New Name",
            avatar="https://example.com/new.png",
            personality="Very helpful",
        )

    assert set(result.updated_fields) == {"name", "avatar", "personality"}


@pytest.mark.asyncio
async def test_update_self_no_fields(mock_lead_runtime):
    """Returns no-op message when no fields provided."""
    from intentkit.core.lead.tools.update_self import LeadUpdateSelf

    tool = LeadUpdateSelf()
    result = await tool._arun()

    assert result.updated_fields == []
    assert "No fields" in result.message


@pytest.mark.asyncio
async def test_update_self_name_truncation(mock_lead_runtime):
    """Name is truncated to 50 characters."""
    from intentkit.core.lead.tools.update_self import LeadUpdateSelf

    long_name = "A" * 100
    captured_updates = {}

    async def mock_update(team_id, updates):
        captured_updates.update(updates)
        return updates

    tool = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.tools.update_self.Team.update_lead_agent_config",
            side_effect=mock_update,
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache"),
    ):
        await tool._arun(name=long_name)

    assert len(captured_updates["name"]) == 50


# ──────────────────────────────────────────────
# LeadUpdateSelfMemory
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_self_memory(mock_lead_runtime):
    """Updates lead agent memory via the shared update_memory function."""
    from intentkit.core.lead.tools.update_self_memory import LeadUpdateSelfMemory

    tool = LeadUpdateSelfMemory()
    with patch(
        "intentkit.core.memory.update_scoped_memory",
        new=AsyncMock(return_value="merged memory content"),
    ) as mock_update:
        result = await tool._arun(content="New info to remember")

    mock_update.assert_called_once_with(
        "team-test-team", "team", "test-team", "New info to remember"
    )
    assert "merged memory content" in result
    assert "updated successfully" in result


# ──────────────────────────────────────────────
# LeadRecentTeamActivities
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_team_activities_found(mock_lead_runtime):
    """Returns formatted activities from team feed."""
    from intentkit.core.lead.tools.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    mock_activity = MagicMock()
    mock_activity.id = "act_1"
    mock_activity.agent_name = "Agent One"
    mock_activity.agent_id = "agent-1"
    mock_activity.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    mock_activity.text = "Did something important"
    mock_activity.images = None
    mock_activity.video = None
    mock_activity.link = None
    mock_activity.post_id = None

    tool = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([mock_activity], None)),
    ):
        result = await tool._arun()

    assert "1 recent team activities" in result
    assert "Agent One" in result
    assert "Did something important" in result


@pytest.mark.asyncio
async def test_recent_team_activities_empty(mock_lead_runtime):
    """Returns no activities message when feed is empty."""
    from intentkit.core.lead.tools.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    tool = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([], None)),
    ):
        result = await tool._arun()

    assert "No recent activities" in result


@pytest.mark.asyncio
async def test_recent_team_activities_with_link(mock_lead_runtime):
    """Activities with links include the link in output."""
    from intentkit.core.lead.tools.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    mock_activity = MagicMock()
    mock_activity.id = "act_2"
    mock_activity.agent_name = "Agent Two"
    mock_activity.agent_id = "agent-2"
    mock_activity.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    mock_activity.text = "Check this link"
    mock_activity.images = ["https://example.com/img.png"]
    mock_activity.video = None
    mock_activity.link = "https://example.com"
    mock_activity.post_id = "post_1"

    tool = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([mock_activity], None)),
    ):
        result = await tool._arun()

    assert "https://example.com" in result
    assert "post_1" in result
    assert "https://example.com/img.png" in result


# ──────────────────────────────────────────────
# LeadRecentTeamPosts
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_team_posts_found(mock_lead_runtime):
    """Returns formatted posts from team feed."""
    from intentkit.core.lead.tools.recent_team_posts import LeadRecentTeamPosts

    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.agent_name = "Agent One"
    mock_post.title = "Great Post"
    mock_post.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    mock_post.slug = "great-post"
    mock_post.excerpt = "A summary"
    mock_post.tags = ["tag1", "tag2"]
    mock_post.cover = None

    tool = LeadRecentTeamPosts()
    with patch(
        "intentkit.core.team.feed.query_post_feed",
        new=AsyncMock(return_value=([mock_post], None)),
    ):
        result = await tool._arun()

    assert "1 recent team posts" in result
    assert "Great Post" in result
    assert "Agent One" in result


@pytest.mark.asyncio
async def test_recent_team_posts_empty(mock_lead_runtime):
    """Returns no posts message when feed is empty."""
    from intentkit.core.lead.tools.recent_team_posts import LeadRecentTeamPosts

    tool = LeadRecentTeamPosts()
    with patch(
        "intentkit.core.team.feed.query_post_feed",
        new=AsyncMock(return_value=([], None)),
    ):
        result = await tool._arun()

    assert "No recent posts" in result


# ──────────────────────────────────────────────
# LeadGetPost
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lead_get_post_success(mock_lead_runtime):
    """Returns full post content by ID."""
    from intentkit.core.lead.tools.get_post import LeadGetPost

    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.agent_name = "Agent One"
    mock_post.title = "Test Post"
    mock_post.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    mock_post.slug = "test-post"
    mock_post.excerpt = "An excerpt"
    mock_post.tags = ["tag1"]
    mock_post.cover = None
    mock_post.markdown = "# Full Content"
    mock_post.agent_id = "agent-1"

    tool = LeadGetPost()
    with (
        patch(
            "intentkit.core.agent_post.get_agent_post",
            new=AsyncMock(return_value=mock_post),
        ),
        patch(
            "intentkit.core.lead.service.verify_agent_in_team",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await tool._arun(post_id="post_1")

    assert "Test Post" in result
    assert "# Full Content" in result
    assert "Agent One" in result


@pytest.mark.asyncio
async def test_lead_get_post_not_found(mock_lead_runtime):
    """Returns not found message for missing post."""
    from intentkit.core.lead.tools.get_post import LeadGetPost

    tool = LeadGetPost()
    with patch(
        "intentkit.core.agent_post.get_agent_post",
        new=AsyncMock(return_value=None),
    ):
        result = await tool._arun(post_id="nonexistent")

    assert "not found" in result


# ──────────────────────────────────────────────
# Sub-agent builders
# ──────────────────────────────────────────────


def test_build_self_updater():
    """Self-updater sub-agent builds correctly."""
    from intentkit.core.lead.sub_agents.self_updater import build_self_updater

    agent = build_self_updater("test-team")
    assert agent.id == "team-test-team-self-updater"
    assert agent.team_id == "test-team"
    assert agent.name == "Self Updater"


def test_build_content_manager():
    """Content manager sub-agent builds correctly."""
    from intentkit.core.lead.sub_agents.content_manager import build_content_manager

    agent = build_content_manager("test-team")
    assert agent.id == "team-test-team-content-manager"
    assert agent.team_id == "test-team"
    assert agent.name == "Content Manager"


def test_self_updater_tools():
    """Self-updater returns expected tools."""
    from intentkit.core.lead.sub_agents.self_updater import get_self_updater_tools

    tools = get_self_updater_tools()
    names = {s.name for s in tools}
    assert names == {
        "lead_get_self_info",
        "lead_update_self",
        "lead_update_self_memory",
    }


def test_content_manager_tools():
    """Content manager returns expected tools."""
    from intentkit.core.lead.sub_agents.content_manager import (
        get_content_manager_tools,
    )

    tools = get_content_manager_tools()
    names = {s.name for s in tools}
    assert names == {
        "lead_recent_team_activities",
        "lead_recent_team_posts",
        "lead_get_post",
    }


# ──────────────────────────────────────────────
# Sub-agent registry
# ──────────────────────────────────────────────


def test_registry_contains_new_sub_agents():
    """Registry includes self-updater, content-manager, and user-manager."""
    from intentkit.core.lead.sub_agents import SUB_AGENT_REGISTRY

    assert "self-updater" in SUB_AGENT_REGISTRY
    assert "content-manager" in SUB_AGENT_REGISTRY
    assert "user-manager" in SUB_AGENT_REGISTRY
    assert SUB_AGENT_REGISTRY["self-updater"].slug == "self-updater"
    assert SUB_AGENT_REGISTRY["content-manager"].slug == "content-manager"
    assert SUB_AGENT_REGISTRY["user-manager"].slug == "user-manager"


# ──────────────────────────────────────────────
# User Manager sub-agent
# ──────────────────────────────────────────────


def test_build_user_manager():
    """User-manager sub-agent builds correctly."""
    from intentkit.core.lead.sub_agents.user_manager import build_user_manager

    agent = build_user_manager("test-team")
    assert agent.id == "team-test-team-user-manager"
    assert agent.team_id == "test-team"
    assert agent.name == "User Manager"


def test_user_manager_tools():
    """User-manager returns expected tools."""
    from intentkit.core.lead.sub_agents.user_manager import get_user_manager_tools

    tools = get_user_manager_tools()
    names = {s.name for s in tools}
    assert names == {"lead_update_user_profile"}


# ──────────────────────────────────────────────
# LeadUpdateUserProfile
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_user_profile_no_user_id():
    """Raises when context has no user_id."""
    from langchain_core.tools.base import ToolException

    from intentkit.core.lead.tools.update_user_profile import LeadUpdateUserProfile

    mock_context = MagicMock(spec=AgentContext)
    mock_context.user_id = None

    tool = LeadUpdateUserProfile()
    with patch("intentkit.tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        with pytest.raises(ToolException, match="No user_id in context"):
            await tool._arun(name="Alice")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_tz", ["Asia/Foobar", "/UTC", "../UTC"])
async def test_update_user_profile_invalid_timezone(mock_lead_runtime, bad_tz):
    """Rejects timezone strings that are not valid IANA names."""
    from langchain_core.tools.base import ToolException

    from intentkit.core.lead.tools.update_user_profile import LeadUpdateUserProfile

    tool = LeadUpdateUserProfile()
    with pytest.raises(ToolException, match="Invalid IANA timezone"):
        await tool._arun(timezone=bad_tz)


@pytest.mark.asyncio
async def test_update_user_profile_no_fields(mock_lead_runtime):
    """Returns empty updated_fields when no usable input is given."""
    from intentkit.core.lead.tools.update_user_profile import LeadUpdateUserProfile

    tool = LeadUpdateUserProfile()
    result = await tool._arun()
    assert result.updated_fields == []
    assert "No fields" in result.message


@pytest.mark.asyncio
async def test_update_user_profile_happy_path(mock_lead_runtime):
    """Patches the user with the provided fields and invalidates cache."""
    from intentkit.core.lead.tools.update_user_profile import LeadUpdateUserProfile

    tool = LeadUpdateUserProfile()

    captured: dict[str, object] = {}

    async def fake_patch(self, user_id):
        captured["user_id"] = user_id
        captured["dump"] = self.model_dump(exclude_unset=True)
        return MagicMock()

    mock_redis = MagicMock()
    mock_redis.delete = AsyncMock()

    with (
        patch(
            "intentkit.core.lead.tools.update_user_profile.UserUpdate.patch",
            new=fake_patch,
        ),
        patch(
            "intentkit.core.lead.tools.update_user_profile.get_redis",
            return_value=mock_redis,
        ),
    ):
        result = await tool._arun(
            name="  Alice  ",
            timezone="Asia/Shanghai",
            language="zh-CN",
        )

    assert captured["user_id"] == "user_1"
    assert captured["dump"] == {
        "name": "Alice",
        "timezone": "Asia/Shanghai",
        "language": "zh-CN",
    }
    assert set(result.updated_fields) == {"name", "timezone", "language"}
    mock_redis.delete.assert_awaited_once_with("intentkit:user:user_1")


@pytest.mark.asyncio
async def test_update_user_profile_clear_with_empty_string(mock_lead_runtime):
    """Empty strings clear timezone and language; name is unaffected."""
    from intentkit.core.lead.tools.update_user_profile import LeadUpdateUserProfile

    tool = LeadUpdateUserProfile()

    captured: dict[str, object] = {}

    async def fake_patch(self, user_id):
        captured["dump"] = self.model_dump(exclude_unset=True)
        return MagicMock()

    mock_redis = MagicMock()
    mock_redis.delete = AsyncMock()

    with (
        patch(
            "intentkit.core.lead.tools.update_user_profile.UserUpdate.patch",
            new=fake_patch,
        ),
        patch(
            "intentkit.core.lead.tools.update_user_profile.get_redis",
            return_value=mock_redis,
        ),
    ):
        result = await tool._arun(timezone="", language="   ")

    assert captured["dump"] == {"timezone": None, "language": None}
    assert set(result.updated_fields) == {"timezone", "language"}
