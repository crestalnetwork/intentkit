"""Unit tests for core share-link functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.core.share_link as share_link_module
from intentkit.core.share_link import (
    SHARE_LINK_DEFAULT_TTL,
    create_share_link,
    get_share_link,
    increment_share_link_view_count,
)
from intentkit.models.share_link import ShareLink, ShareLinkTargetType


def _make_db_link(**overrides) -> MagicMock:
    """Build a MagicMock that mimics a ShareLinkTable row."""
    now = datetime.now(UTC)
    base = {
        "id": "sl-existing",
        "target_type": ShareLinkTargetType.POST.value,
        "target_id": "post-1",
        "agent_id": "agent-1",
        "user_id": None,
        "team_id": None,
        "view_count": 0,
        "created_at": now,
        "expires_at": now + SHARE_LINK_DEFAULT_TTL,
    }
    base.update(overrides)
    m = MagicMock()
    for key, value in base.items():
        setattr(m, key, value)
    return m


def _install_session(monkeypatch, *, existing_row):
    """Wire up get_session() to yield a mocked AsyncSession."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = existing_row
    mock_session.execute.return_value = exec_result

    refreshed = {"created": None}

    async def _refresh(obj):
        obj.id = "sl-new"
        obj.created_at = datetime.now(UTC)
        obj.view_count = 0
        refreshed["created"] = obj

    mock_session.refresh.side_effect = _refresh

    ctx = MagicMock()
    ctx.__aenter__.return_value = mock_session
    ctx.__aexit__.return_value = None
    monkeypatch.setattr(share_link_module, "get_session", lambda: ctx)
    return mock_session, refreshed


@pytest.mark.asyncio
async def test_create_share_link_reuses_fresh_link(monkeypatch):
    existing = _make_db_link()
    session, refreshed = _install_session(monkeypatch, existing_row=existing)

    link = await create_share_link(ShareLinkTargetType.POST, "post-1", "agent-1")

    assert link.id == "sl-existing"
    session.add.assert_not_called()
    assert refreshed["created"] is None


@pytest.mark.asyncio
async def test_create_share_link_creates_new_when_below_half_ttl(monkeypatch):
    # No row past the reuse_threshold -> scalar_one_or_none returns None
    session, refreshed = _install_session(monkeypatch, existing_row=None)

    link = await create_share_link(
        ShareLinkTargetType.POST,
        "post-1",
        "agent-1",
        user_id="u-1",
        team_id="team-1",
    )

    assert link.id == "sl-new"
    session.add.assert_called_once()
    inserted = session.add.call_args.args[0]
    assert inserted.target_type == ShareLinkTargetType.POST.value
    assert inserted.target_id == "post-1"
    assert inserted.agent_id == "agent-1"
    assert inserted.user_id == "u-1"
    assert inserted.team_id == "team-1"
    assert inserted.expires_at > datetime.now(UTC) + timedelta(days=2)


@pytest.mark.asyncio
async def test_create_share_link_reuse_keeps_original_creator(monkeypatch):
    """Reusing an existing link must not overwrite its stored user_id/team_id."""
    existing = _make_db_link(user_id="original-user", team_id="original-team")
    session, _refreshed = _install_session(monkeypatch, existing_row=existing)

    link = await create_share_link(
        ShareLinkTargetType.POST,
        "post-1",
        "agent-1",
        user_id="new-user",
        team_id="new-team",
    )

    assert link.id == "sl-existing"
    assert link.user_id == "original-user"
    assert link.team_id == "original-team"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_share_link_returns_none_when_expired(monkeypatch):
    past = datetime.now(UTC) - timedelta(minutes=5)
    db_row = _make_db_link(expires_at=past)

    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = db_row
    mock_session.execute.return_value = exec_result
    ctx = MagicMock()
    ctx.__aenter__.return_value = mock_session
    ctx.__aexit__.return_value = None
    monkeypatch.setattr(share_link_module, "get_session", lambda: ctx)

    redis_client = AsyncMock()
    redis_client.get.return_value = None
    monkeypatch.setattr(share_link_module, "get_redis", lambda: redis_client)

    assert await get_share_link("sl-existing") is None


@pytest.mark.asyncio
async def test_increment_share_link_view_count(monkeypatch):
    """Increment issues a single UPDATE + commit against the share_links table."""
    mock_session = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__.return_value = mock_session
    ctx.__aexit__.return_value = None
    monkeypatch.setattr(share_link_module, "get_session", lambda: ctx)

    await increment_share_link_view_count("sl-abc")

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_share_link_returns_cached_value(monkeypatch):
    future = datetime.now(UTC) + timedelta(days=1)
    cached = ShareLink(
        id="sl-cache",
        target_type=ShareLinkTargetType.POST,
        target_id="post-1",
        agent_id="agent-1",
        created_at=datetime.now(UTC),
        expires_at=future,
    )

    redis_client = AsyncMock()
    redis_client.get.return_value = cached.model_dump_json()
    monkeypatch.setattr(share_link_module, "get_redis", lambda: redis_client)

    # DB should not be queried when cache is hot; install a session that would fail.
    def _unexpected():
        raise AssertionError("get_session should not be called on cache hit")

    monkeypatch.setattr(share_link_module, "get_session", _unexpected)

    link = await get_share_link("sl-cache")
    assert link is not None
    assert link.id == "sl-cache"
