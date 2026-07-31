"""Tests for the lead's public-agent follow/unfollow tools and prompt injection."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.abstracts.graph import AgentContext
from intentkit.utils.error import IntentKitAPIError


@pytest.fixture
def mock_lead_runtime():
    """Mocked runtime context with a team_id for lead tools."""
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = "team-test-team"
    mock_context.team_id = "test-team"
    mock_context.chat_id = "chat_1"
    mock_context.user_id = "user_1"

    with patch("intentkit.tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


def _agent(
    agent_id="a1",
    name="Agent",
    slug=None,
    visibility=20,
    description=None,
):
    a = MagicMock()
    a.id = agent_id
    a.name = name
    a.slug = slug
    a.description = description
    a.model = "gpt-4o"
    a.owner = "owner-1"
    a.team_id = "other-team"
    a.visibility = visibility
    a.archived_at = None
    return a


# ──────────────────────────────────────────────
# LeadListPublicAgents
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_public_agents_marks_followed(mock_lead_runtime):
    from intentkit.core.lead.tools.list_public_agents import LeadListPublicAgents

    agents = [_agent("a1", "One"), _agent("a2", "Two")]

    tool = LeadListPublicAgents()
    with (
        patch(
            "intentkit.core.lead.tools.list_public_agents.list_public_agents",
            new=AsyncMock(return_value=agents),
        ),
        patch(
            "intentkit.core.lead.tools.list_public_agents.get_followed_agent_ids",
            new=AsyncMock(return_value={"a2"}),
        ),
    ):
        result = await tool._arun(search="x", limit=10)

    by_id = {a.id: a for a in result.agents}
    assert by_id["a1"].followed is False
    assert by_id["a2"].followed is True


# ──────────────────────────────────────────────
# LeadFollowAgent
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_follow_agent_success(mock_lead_runtime):
    from intentkit.core.lead.tools.follow_agent import LeadFollowAgent

    resolved = _agent("a1", "Public Agent", slug="public-agent")

    tool = LeadFollowAgent()
    with (
        patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=resolved),
        ),
        patch("intentkit.core.team.subscribe_agent", new=AsyncMock()) as mock_subscribe,
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        result = await tool._arun(agent_id="public-agent")

    assert result.agent_id == "a1"
    assert result.name == "Public Agent"
    mock_subscribe.assert_awaited_once_with("test-team", "a1")
    mock_invalidate.assert_called_once_with("test-team")


@pytest.mark.asyncio
async def test_follow_agent_not_found(mock_lead_runtime):
    from intentkit.core.lead.tools.follow_agent import LeadFollowAgent

    tool = LeadFollowAgent()
    with patch(
        "intentkit.core.agent.queries.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(ToolException, match="not found"):
            await tool._arun(agent_id="ghost")


@pytest.mark.asyncio
async def test_follow_agent_not_public_raises_tool_exception(mock_lead_runtime):
    from intentkit.core.lead.tools.follow_agent import LeadFollowAgent

    resolved = _agent("a1", "Private Agent", visibility=0)

    tool = LeadFollowAgent()
    with (
        patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=resolved),
        ),
        patch(
            "intentkit.core.team.subscribe_agent",
            new=AsyncMock(
                side_effect=IntentKitAPIError(403, "Forbidden", "Agent is not public")
            ),
        ),
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        with pytest.raises(ToolException, match="not public"):
            await tool._arun(agent_id="a1")

        # Cache must not be invalidated when the follow fails.
        mock_invalidate.assert_not_called()


# ──────────────────────────────────────────────
# LeadUnfollowAgent
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unfollow_agent_success(mock_lead_runtime):
    from intentkit.core.lead.tools.unfollow_agent import LeadUnfollowAgent

    resolved = _agent("a1", "Public Agent", slug="public-agent")

    tool = LeadUnfollowAgent()
    with (
        patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=resolved),
        ),
        patch("intentkit.core.team.unsubscribe_agent", new=AsyncMock()) as mock_unsub,
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        result = await tool._arun(agent_id="public-agent")

    assert result.agent_id == "a1"
    mock_unsub.assert_awaited_once_with("test-team", "a1")
    mock_invalidate.assert_called_once_with("test-team")


@pytest.mark.asyncio
async def test_unfollow_agent_refuses_own_team(mock_lead_runtime):
    """Unfollowing a team's own agent is refused to protect its feed history."""
    from intentkit.core.lead.tools.unfollow_agent import LeadUnfollowAgent

    own = _agent("own-1", "Own Agent", slug="own-agent")
    own.team_id = "test-team"  # same as context.team_id

    tool = LeadUnfollowAgent()
    with (
        patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=own),
        ),
        patch("intentkit.core.team.unsubscribe_agent", new=AsyncMock()) as mock_unsub,
        patch("intentkit.core.lead.cache.invalidate_lead_cache") as mock_invalidate,
    ):
        with pytest.raises(ToolException, match="own team"):
            await tool._arun(agent_id="own-agent")

        mock_unsub.assert_not_called()
        mock_invalidate.assert_not_called()


@pytest.mark.asyncio
async def test_unfollow_agent_falls_back_to_raw_id(mock_lead_runtime):
    """A subscription to a since-deleted agent can still be cleared by raw ID."""
    from intentkit.core.lead.tools.unfollow_agent import LeadUnfollowAgent

    tool = LeadUnfollowAgent()
    with (
        patch(
            "intentkit.core.agent.queries.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=None),
        ),
        patch("intentkit.core.team.unsubscribe_agent", new=AsyncMock()) as mock_unsub,
        patch("intentkit.core.lead.cache.invalidate_lead_cache"),
    ):
        result = await tool._arun(agent_id="deleted-id")

    assert result.agent_id == "deleted-id"
    mock_unsub.assert_awaited_once_with("test-team", "deleted-id")


# ──────────────────────────────────────────────
# _build_followed_agents_section
# ──────────────────────────────────────────────


def test_followed_agents_section_empty():
    from intentkit.core.lead.engine import (
        _build_followed_agents_section,
    )

    assert _build_followed_agents_section([]) == ""


def test_followed_agents_section_lists_agents():
    from intentkit.core.lead.engine import (
        _build_followed_agents_section,
    )

    agents = [
        _agent(
            "a1",
            "Finance Bot",
            slug="finance-bot",
            description="Your friendly markets analyst",
        ),
        # No description -> name only, id label fallback.
        _agent("a3", "Quiet", slug=None),
    ]
    section = _build_followed_agents_section(agents)  # pyright: ignore[reportArgumentType]

    assert "### Followed Agents" in section
    assert "`finance-bot` (Finance Bot): Your friendly markets analyst" in section
    # Falls back to id as the label when slug is missing, name still shown.
    assert "`a3` (Quiet)" in section


# ──────────────────────────────────────────────
# lead_call_agent cross-team public delegation
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_db_agent_allows_followed_public_cross_team(mock_lead_runtime):
    from intentkit.core.lead.tools.call_agent import LeadCallAgent
    from intentkit.models.chat import AuthorType

    _, context = mock_lead_runtime
    context.call_depth = 0
    context.entrypoint = None

    public_agent = _agent("ext-1", "Public", visibility=20)
    public_agent.team_id = "another-team"

    agent_msg = MagicMock()
    agent_msg.author_type = AuthorType.AGENT
    agent_msg.message = "done"
    agent_msg.attachments = []

    tool = LeadCallAgent()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=public_agent),
        ),
        patch(
            "intentkit.core.lead.service.is_agent_followed",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "intentkit.core.engine.execute_agent",
            new=AsyncMock(return_value=[agent_msg]),
        ) as mock_execute,
        patch(
            "intentkit.core.lead.tools.call_agent.render_attachments_awareness",
            return_value="",
        ),
    ):
        text, _attachments = await tool._call_db_agent(context, "ext-1", "hi", None)

    assert text == "done"
    mock_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_db_agent_rejects_unfollowed_public_cross_team(mock_lead_runtime):
    from intentkit.core.lead.tools.call_agent import LeadCallAgent

    _, context = mock_lead_runtime
    context.call_depth = 0
    context.entrypoint = None

    public_agent = _agent("ext-1", "Public", visibility=20)
    public_agent.team_id = "another-team"

    tool = LeadCallAgent()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=public_agent),
        ),
        patch(
            "intentkit.core.lead.service.is_agent_followed",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(ToolException, match="follow it first"):
            await tool._call_db_agent(context, "ext-1", "hi", None)


@pytest.mark.asyncio
async def test_call_db_agent_rejects_private_cross_team(mock_lead_runtime):
    from intentkit.core.lead.tools.call_agent import LeadCallAgent

    _, context = mock_lead_runtime
    context.call_depth = 0
    context.entrypoint = None

    private_agent = _agent("ext-2", "Private", visibility=0)
    private_agent.team_id = "another-team"

    tool = LeadCallAgent()
    with (
        patch(
            "intentkit.core.agent.get_agent_by_id_or_slug",
            new=AsyncMock(return_value=private_agent),
        ),
        # is_agent_followed is short-circuited for non-public agents, but patch
        # it defensively so the test never touches the DB.
        patch(
            "intentkit.core.lead.service.is_agent_followed",
            new=AsyncMock(return_value=True),
        ),
    ):
        with pytest.raises(ToolException, match="not accessible"):
            await tool._call_db_agent(context, "ext-2", "hi", None)


@pytest.mark.asyncio
async def test_call_db_agent_rejects_archived(mock_lead_runtime):
    from intentkit.core.lead.tools.call_agent import LeadCallAgent

    _, context = mock_lead_runtime
    context.call_depth = 0
    context.entrypoint = None

    # An own-team agent that happens to be archived must not be callable.
    archived = _agent("own-1", "Archived", visibility=10)
    archived.team_id = "test-team"
    archived.archived_at = datetime.now(UTC)

    tool = LeadCallAgent()
    with patch(
        "intentkit.core.agent.get_agent_by_id_or_slug",
        new=AsyncMock(return_value=archived),
    ):
        with pytest.raises(ToolException, match="archived"):
            await tool._call_db_agent(context, "own-1", "hi", None)
