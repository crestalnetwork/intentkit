"""Tests for intentkit/core/agent/publish.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.public_info import AgentPublicInfo
from intentkit.utils.error import IntentKitAPIError

MODULE = "intentkit.core.agent.publish"


def _mock_session():
    """Return (session_ctx, session) where session is the AsyncMock used inside."""
    session = AsyncMock()
    session.add = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, session


def _make_db_agent(
    *,
    agent_id: str = "agent-1",
    team_id: str | None = "team-1",
    visibility: AgentVisibility | None = None,
    archived: bool = False,
):
    """Build a MagicMock that behaves like an AgentTable row."""
    agent = MagicMock()
    agent.id = agent_id
    agent.team_id = team_id
    agent.visibility = visibility
    agent.archived_at = "2026-01-01" if archived else None
    # Public-info attributes the helper writes back onto the row. Using a
    # MagicMock means any setattr() succeeds; explicit defaults make the
    # before/after comparisons readable.
    agent.description = None
    agent.x402_price = 0.01
    agent.examples = None
    agent.tags = None
    agent.public_info_updated_at = None
    return agent


def _wire_select_agent(session, db_agent):
    """Make session.execute(select(AgentTable)...) return a result whose
    scalar_one_or_none() yields *db_agent*."""
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = db_agent
    session.execute = AsyncMock(return_value=select_result)


# ---------------------------------------------------------------------------
# publish_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_publish_agent_not_found(mock_get_session):
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    _wire_select_agent(session, None)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await publish_agent(agent_id="missing", public_info=AgentPublicInfo())

    assert exc_info.value.status_code == 404
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_publish_agent_no_team_id(mock_get_session):
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent(team_id=None)
    _wire_select_agent(session, db_agent)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await publish_agent(agent_id="agent-1", public_info=AgentPublicInfo())

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "AgentHasNoTeam"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_publish_agent_team_not_found(mock_get_session):
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent()
    _wire_select_agent(session, db_agent)
    session.get = AsyncMock(return_value=None)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await publish_agent(agent_id="agent-1", public_info=AgentPublicInfo())

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "TeamNotFound"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_publish_agent_limit_reached(mock_get_session):
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent()
    _wire_select_agent(session, db_agent)
    team = MagicMock()
    team.public_agent_limit = 1
    session.get = AsyncMock(return_value=team)
    session.scalar = AsyncMock(return_value=1)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await publish_agent(agent_id="agent-1", public_info=AgentPublicInfo())

    assert exc_info.value.status_code == 403
    assert exc_info.value.key == "PublicAgentLimitReached"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_publish_agent_zero_limit_blocks_first_publish(mock_get_session):
    """A team with public_agent_limit=0 cannot publish even its first agent."""
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent()
    _wire_select_agent(session, db_agent)
    team = MagicMock()
    team.public_agent_limit = 0
    session.get = AsyncMock(return_value=team)
    session.scalar = AsyncMock(return_value=0)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await publish_agent(agent_id="agent-1", public_info=AgentPublicInfo())

    assert exc_info.value.status_code == 403
    assert exc_info.value.key == "PublicAgentLimitReached"


@pytest.mark.asyncio
@patch("intentkit.models.agent.Agent")
@patch(f"{MODULE}.get_session")
async def test_publish_agent_under_limit_writes_public_info(
    mock_get_session, mock_agent_cls
):
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent()
    _wire_select_agent(session, db_agent)
    team = MagicMock()
    team.public_agent_limit = 5
    session.get = AsyncMock(return_value=team)
    session.scalar = AsyncMock(return_value=0)
    mock_agent_cls.model_validate.return_value = MagicMock()

    public_info = AgentPublicInfo(description="Hello world", x402_price=0.5)
    await publish_agent(agent_id="agent-1", public_info=public_info)

    assert db_agent.visibility == AgentVisibility.PUBLIC
    assert db_agent.description == "Hello world"
    assert db_agent.x402_price == 0.5
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(db_agent)


@pytest.mark.asyncio
@patch("intentkit.models.agent.Agent")
@patch(f"{MODULE}.get_session")
async def test_publish_agent_already_public_skips_quota(
    mock_get_session, mock_agent_cls
):
    """Re-publishing should not consult the limit so operators can edit
    existing public info even when the team is already at quota."""
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent(visibility=AgentVisibility.PUBLIC)
    _wire_select_agent(session, db_agent)
    session.get = AsyncMock()  # Should never be called.
    session.scalar = AsyncMock()  # Should never be called.
    mock_agent_cls.model_validate.return_value = MagicMock()

    public_info = AgentPublicInfo(description="Updated")
    await publish_agent(agent_id="agent-1", public_info=public_info)

    session.get.assert_not_awaited()
    session.scalar.assert_not_awaited()
    assert db_agent.visibility == AgentVisibility.PUBLIC
    assert db_agent.description == "Updated"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("intentkit.models.agent.Agent")
@patch(f"{MODULE}.get_session")
async def test_publish_agent_uses_exclude_unset(mock_get_session, mock_agent_cls):
    """Only fields explicitly provided should overwrite existing values."""
    from intentkit.core.agent.publish import publish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent()
    db_agent.description = "existing description"
    db_agent.x402_price = 0.99
    _wire_select_agent(session, db_agent)
    team = MagicMock()
    team.public_agent_limit = 5
    session.get = AsyncMock(return_value=team)
    session.scalar = AsyncMock(return_value=0)
    mock_agent_cls.model_validate.return_value = MagicMock()

    # Caller only sets `tags` — description/x402_price must be preserved.
    public_info = AgentPublicInfo.model_validate({"tags": ["alpha"]})
    await publish_agent(agent_id="agent-1", public_info=public_info)

    assert db_agent.tags == ["alpha"]
    assert db_agent.description == "existing description"
    assert db_agent.x402_price == 0.99


# ---------------------------------------------------------------------------
# unpublish_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch(f"{MODULE}.get_session")
async def test_unpublish_agent_not_found(mock_get_session):
    from intentkit.core.agent.publish import unpublish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    _wire_select_agent(session, None)

    with pytest.raises(IntentKitAPIError) as exc_info:
        await unpublish_agent(agent_id="missing")

    assert exc_info.value.status_code == 404
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch("intentkit.models.agent.Agent")
@patch(f"{MODULE}.get_session")
async def test_unpublish_agent_idempotent_when_already_team(
    mock_get_session, mock_agent_cls
):
    """Unpublishing an agent that's already TEAM-visible should still succeed
    and clear any stale subscriptions left over."""
    from intentkit.core.agent.publish import unpublish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent(visibility=AgentVisibility.TEAM)

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = db_agent
    ref_check_result = MagicMock()
    ref_check_result.all.return_value = []
    delete_result = MagicMock()
    session.execute = AsyncMock(
        side_effect=[select_result, ref_check_result, delete_result]
    )
    mock_agent_cls.model_validate.return_value = MagicMock()

    await unpublish_agent(agent_id="agent-1")

    assert db_agent.visibility == AgentVisibility.TEAM
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("intentkit.models.agent.Agent")
@patch(f"{MODULE}.get_session")
async def test_unpublish_agent_clears_subscriptions_only(
    mock_get_session, mock_agent_cls
):
    """unpublish flips visibility to TEAM and runs exactly one DELETE
    (subscriptions). Activity / post feed entries must NOT be touched."""
    from intentkit.core.agent.publish import unpublish_agent

    ctx, session = _mock_session()
    mock_get_session.return_value = ctx
    db_agent = _make_db_agent(visibility=AgentVisibility.PUBLIC)

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = db_agent
    ref_check_result = MagicMock()
    ref_check_result.all.return_value = []
    delete_result = MagicMock()
    # SELECT agent, then the public-reference check, then the DELETE.
    session.execute = AsyncMock(
        side_effect=[select_result, ref_check_result, delete_result]
    )
    mock_agent_cls.model_validate.return_value = MagicMock()

    await unpublish_agent(agent_id="agent-1")

    assert db_agent.visibility == AgentVisibility.TEAM
    # Exactly three execute calls: agent SELECT + reference check + one
    # DELETE against team_subscriptions. No deletes against feed tables.
    assert session.execute.await_count == 3
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(db_agent)
