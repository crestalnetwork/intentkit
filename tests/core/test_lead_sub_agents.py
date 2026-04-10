"""Tests for lead sub-agents: self-updater and content-manager."""

from datetime import datetime, timezone
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

    with patch("intentkit.skills.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


# ──────────────────────────────────────────────
# LeadGetSelfInfo
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_self_info_defaults(mock_lead_runtime):
    """Returns default values when no persisted config exists."""
    from intentkit.core.lead.skills.get_self_info import LeadGetSelfInfo

    mock_agent_data = MagicMock()
    mock_agent_data.long_term_memory = None

    skill = LeadGetSelfInfo()
    with (
        patch(
            "intentkit.core.lead.skills.get_self_info.Team.get_lead_agent_config",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "intentkit.core.lead.skills.get_self_info.AgentData.get",
            new=AsyncMock(return_value=mock_agent_data),
        ),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert result.name == "Team Lead"
    assert result.avatar is None
    assert "Helpful team assistant" in result.personality
    assert result.memory is None


@pytest.mark.asyncio
async def test_get_self_info_with_config(mock_lead_runtime):
    """Returns persisted config values when they exist."""
    from intentkit.core.lead.skills.get_self_info import LeadGetSelfInfo

    mock_agent_data = MagicMock()
    mock_agent_data.long_term_memory = "I remember things"

    skill = LeadGetSelfInfo()
    with (
        patch(
            "intentkit.core.lead.skills.get_self_info.Team.get_lead_agent_config",
            new=AsyncMock(
                return_value={
                    "name": "Custom Lead",
                    "avatar": "https://example.com/avatar.png",
                    "personality": "Friendly and professional",
                }
            ),
        ),
        patch(
            "intentkit.core.lead.skills.get_self_info.AgentData.get",
            new=AsyncMock(return_value=mock_agent_data),
        ),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

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
    from intentkit.core.lead.skills.update_self import LeadUpdateSelf

    skill = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.skills.update_self.Team.update_lead_agent_config",
            new=AsyncMock(return_value={"name": "New Name"}),
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        result = await skill._arun(name="New Name")  # pyright: ignore[reportPrivateUsage]

    assert "name" in result.updated_fields
    assert result.message == "Lead agent updated: name."
    mock_invalidate.assert_called_once_with("test-team")


@pytest.mark.asyncio
async def test_update_self_multiple_fields(mock_lead_runtime):
    """Updates multiple fields at once."""
    from intentkit.core.lead.skills.update_self import LeadUpdateSelf

    skill = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.skills.update_self.Team.update_lead_agent_config",
            new=AsyncMock(return_value={}),
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache"),
    ):
        result = await skill._arun(  # pyright: ignore[reportPrivateUsage]
            name="New Name",
            avatar="https://example.com/new.png",
            personality="Very helpful",
        )

    assert set(result.updated_fields) == {"name", "avatar", "personality"}


@pytest.mark.asyncio
async def test_update_self_no_fields(mock_lead_runtime):
    """Returns no-op message when no fields provided."""
    from intentkit.core.lead.skills.update_self import LeadUpdateSelf

    skill = LeadUpdateSelf()
    result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert result.updated_fields == []
    assert "No fields" in result.message


@pytest.mark.asyncio
async def test_update_self_name_truncation(mock_lead_runtime):
    """Name is truncated to 50 characters."""
    from intentkit.core.lead.skills.update_self import LeadUpdateSelf

    long_name = "A" * 100
    captured_updates = {}

    async def mock_update(team_id, updates):
        captured_updates.update(updates)
        return updates

    skill = LeadUpdateSelf()
    with (
        patch(
            "intentkit.core.lead.skills.update_self.Team.update_lead_agent_config",
            side_effect=mock_update,
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache"),
    ):
        await skill._arun(name=long_name)  # pyright: ignore[reportPrivateUsage]

    assert len(captured_updates["name"]) == 50


# ──────────────────────────────────────────────
# LeadUpdateSelfMemory
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_self_memory(mock_lead_runtime):
    """Updates lead agent memory via the shared update_memory function."""
    from intentkit.core.lead.skills.update_self_memory import LeadUpdateSelfMemory

    skill = LeadUpdateSelfMemory()
    with patch(
        "intentkit.core.memory.update_memory",
        new=AsyncMock(return_value="merged memory content"),
    ) as mock_update:
        result = await skill._arun(content="New info to remember")  # pyright: ignore[reportPrivateUsage]

    mock_update.assert_called_once_with("team-test-team", "New info to remember")
    assert "merged memory content" in result
    assert "updated successfully" in result


# ──────────────────────────────────────────────
# LeadRecentTeamActivities
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_team_activities_found(mock_lead_runtime):
    """Returns formatted activities from team feed."""
    from intentkit.core.lead.skills.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    mock_activity = MagicMock()
    mock_activity.id = "act_1"
    mock_activity.agent_name = "Agent One"
    mock_activity.agent_id = "agent-1"
    mock_activity.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_activity.text = "Did something important"
    mock_activity.images = None
    mock_activity.video = None
    mock_activity.link = None
    mock_activity.post_id = None

    skill = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([mock_activity], None)),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "1 recent team activities" in result
    assert "Agent One" in result
    assert "Did something important" in result


@pytest.mark.asyncio
async def test_recent_team_activities_empty(mock_lead_runtime):
    """Returns no activities message when feed is empty."""
    from intentkit.core.lead.skills.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    skill = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([], None)),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "No recent activities" in result


@pytest.mark.asyncio
async def test_recent_team_activities_with_link(mock_lead_runtime):
    """Activities with links include the link in output."""
    from intentkit.core.lead.skills.recent_team_activities import (
        LeadRecentTeamActivities,
    )

    mock_activity = MagicMock()
    mock_activity.id = "act_2"
    mock_activity.agent_name = "Agent Two"
    mock_activity.agent_id = "agent-2"
    mock_activity.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_activity.text = "Check this link"
    mock_activity.images = ["https://example.com/img.png"]
    mock_activity.video = None
    mock_activity.link = "https://example.com"
    mock_activity.post_id = "post_1"

    skill = LeadRecentTeamActivities()
    with patch(
        "intentkit.core.team.feed.query_activity_feed",
        new=AsyncMock(return_value=([mock_activity], None)),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "https://example.com" in result
    assert "post_1" in result
    assert "https://example.com/img.png" in result


# ──────────────────────────────────────────────
# LeadRecentTeamPosts
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_team_posts_found(mock_lead_runtime):
    """Returns formatted posts from team feed."""
    from intentkit.core.lead.skills.recent_team_posts import LeadRecentTeamPosts

    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.agent_name = "Agent One"
    mock_post.title = "Great Post"
    mock_post.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_post.slug = "great-post"
    mock_post.excerpt = "A summary"
    mock_post.tags = ["tag1", "tag2"]
    mock_post.cover = None

    skill = LeadRecentTeamPosts()
    with patch(
        "intentkit.core.team.feed.query_post_feed",
        new=AsyncMock(return_value=([mock_post], None)),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "1 recent team posts" in result
    assert "Great Post" in result
    assert "Agent One" in result


@pytest.mark.asyncio
async def test_recent_team_posts_empty(mock_lead_runtime):
    """Returns no posts message when feed is empty."""
    from intentkit.core.lead.skills.recent_team_posts import LeadRecentTeamPosts

    skill = LeadRecentTeamPosts()
    with patch(
        "intentkit.core.team.feed.query_post_feed",
        new=AsyncMock(return_value=([], None)),
    ):
        result = await skill._arun()  # pyright: ignore[reportPrivateUsage]

    assert "No recent posts" in result


# ──────────────────────────────────────────────
# LeadGetPost
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lead_get_post_success(mock_lead_runtime):
    """Returns full post content by ID."""
    from intentkit.core.lead.skills.get_post import LeadGetPost

    mock_post = MagicMock()
    mock_post.id = "post_1"
    mock_post.agent_name = "Agent One"
    mock_post.title = "Test Post"
    mock_post.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_post.slug = "test-post"
    mock_post.excerpt = "An excerpt"
    mock_post.tags = ["tag1"]
    mock_post.cover = None
    mock_post.markdown = "# Full Content"
    mock_post.agent_id = "agent-1"

    skill = LeadGetPost()
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
        result = await skill._arun(post_id="post_1")  # pyright: ignore[reportPrivateUsage]

    assert "Test Post" in result
    assert "# Full Content" in result
    assert "Agent One" in result


@pytest.mark.asyncio
async def test_lead_get_post_not_found(mock_lead_runtime):
    """Returns not found message for missing post."""
    from intentkit.core.lead.skills.get_post import LeadGetPost

    skill = LeadGetPost()
    with patch(
        "intentkit.core.agent_post.get_agent_post",
        new=AsyncMock(return_value=None),
    ):
        result = await skill._arun(post_id="nonexistent")  # pyright: ignore[reportPrivateUsage]

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


def test_self_updater_skills():
    """Self-updater returns expected skills."""
    from intentkit.core.lead.sub_agents.self_updater import get_self_updater_skills

    skills = get_self_updater_skills()
    names = {s.name for s in skills}
    assert names == {
        "lead_get_self_info",
        "lead_update_self",
        "lead_update_self_memory",
    }


def test_content_manager_skills():
    """Content manager returns expected skills."""
    from intentkit.core.lead.sub_agents.content_manager import (
        get_content_manager_skills,
    )

    skills = get_content_manager_skills()
    names = {s.name for s in skills}
    assert names == {
        "lead_recent_team_activities",
        "lead_recent_team_posts",
        "lead_get_post",
    }


# ──────────────────────────────────────────────
# Sub-agent registry
# ──────────────────────────────────────────────


def test_registry_contains_new_sub_agents():
    """Registry includes self-updater and content-manager."""
    from intentkit.core.lead.sub_agents import SUB_AGENT_REGISTRY

    assert "self-updater" in SUB_AGENT_REGISTRY
    assert "content-manager" in SUB_AGENT_REGISTRY
    assert SUB_AGENT_REGISTRY["self-updater"].slug == "self-updater"
    assert SUB_AGENT_REGISTRY["content-manager"].slug == "content-manager"
