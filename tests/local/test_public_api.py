"""Tests for Public API endpoints (agents, timeline, posts)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent_activity import AgentActivity
from intentkit.models.agent_post import AgentPost, AgentPostBrief


def _get_endpoint(router, path):
    """Extract endpoint function from router by path."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == path:
            return route.endpoint
    raise ValueError(f"Route {path} not found")


@pytest.fixture
def router():
    from intentkit.core.public_api import create_public_router

    return create_public_router()


@pytest.fixture
def public_agent():
    return AgentTable(
        id="public-blog-writer",
        slug="blog-writer",
        name="Blog Writer",
        owner="predefined",
        team_id="predefined",
        model="google/gemini-2.5-flash",
        visibility=AgentVisibility.PUBLIC,
        archived_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def private_agent():
    return AgentTable(
        id="my-private-agent",
        slug="my-private",
        name="Private Agent",
        owner="system",
        team_id="system",
        model="google/gemini-2.5-flash",
        visibility=AgentVisibility.PRIVATE,
        archived_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


# ---- /public/agents tests ----


@pytest.mark.asyncio
async def test_list_public_agents_returns_only_public(router, public_agent):
    """Only agents with visibility >= PUBLIC should be listed."""
    list_fn = _get_endpoint(router, "/public/agents")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [public_agent]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    with patch("intentkit.core.public_api.get_session") as mock_gs:
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("intentkit.core.public_api.AgentResponse") as mock_resp_cls:
            mock_resp = MagicMock()
            mock_resp.id = "public-blog-writer"
            mock_resp_cls.from_agent = AsyncMock(return_value=mock_resp)

            result = await list_fn()

    assert len(result) == 1
    assert result[0].id == "public-blog-writer"


@pytest.mark.asyncio
async def test_list_public_agents_empty(router):
    """Empty result when no public agents exist."""
    list_fn = _get_endpoint(router, "/public/agents")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    with patch("intentkit.core.public_api.get_session") as mock_gs:
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await list_fn()

    assert result == []


# ---- /public/posts/{post_id} visibility check tests ----


@pytest.mark.asyncio
async def test_get_public_post_from_public_agent(router, public_agent):
    """Posts from public agents should be accessible."""
    get_post_fn = _get_endpoint(router, "/public/posts/{post_id}")

    mock_post = MagicMock(spec=AgentPost)
    mock_post.agent_id = "public-blog-writer"

    mock_session = AsyncMock()
    mock_session.get.return_value = public_agent

    with (
        patch(
            "intentkit.core.public_api.get_agent_post", new_callable=AsyncMock
        ) as mock_get_post,
        patch("intentkit.core.public_api.get_session") as mock_gs,
    ):
        mock_get_post.return_value = mock_post
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_post_fn(post_id="post-123")

    assert result == mock_post


@pytest.mark.asyncio
async def test_get_public_post_from_private_agent_returns_404(router, private_agent):
    """Posts from private agents should return 404."""
    from intentkit.utils.error import IntentKitAPIError

    get_post_fn = _get_endpoint(router, "/public/posts/{post_id}")

    mock_post = MagicMock(spec=AgentPost)
    mock_post.agent_id = "my-private-agent"

    mock_session = AsyncMock()
    mock_session.get.return_value = private_agent

    with (
        patch(
            "intentkit.core.public_api.get_agent_post", new_callable=AsyncMock
        ) as mock_get_post,
        patch("intentkit.core.public_api.get_session") as mock_gs,
    ):
        mock_get_post.return_value = mock_post
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_post_fn(post_id="post-123")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_post_nonexistent_returns_404(router):
    """Non-existent posts should return 404."""
    from intentkit.utils.error import IntentKitAPIError

    get_post_fn = _get_endpoint(router, "/public/posts/{post_id}")

    with patch(
        "intentkit.core.public_api.get_agent_post", new_callable=AsyncMock
    ) as mock_get_post:
        mock_get_post.return_value = None

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_post_fn(post_id="nonexistent")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_post_agent_not_found_returns_404(router):
    """Post whose agent doesn't exist should return 404."""
    from intentkit.utils.error import IntentKitAPIError

    get_post_fn = _get_endpoint(router, "/public/posts/{post_id}")

    mock_post = MagicMock(spec=AgentPost)
    mock_post.agent_id = "deleted-agent"

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with (
        patch(
            "intentkit.core.public_api.get_agent_post", new_callable=AsyncMock
        ) as mock_get_post,
        patch("intentkit.core.public_api.get_session") as mock_gs,
    ):
        mock_get_post.return_value = mock_post
        mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_post_fn(post_id="post-orphan")

    assert exc_info.value.status_code == 404


# ---- /public/timeline and /public/posts tests ----


@pytest.mark.asyncio
async def test_public_timeline_calls_correct_team(router):
    """Timeline should query the 'public' virtual team."""
    timeline_fn = _get_endpoint(router, "/public/timeline")

    with patch(
        "intentkit.core.public_api.query_activity_feed", new_callable=AsyncMock
    ) as mock_query:
        mock_activities = [MagicMock(spec=AgentActivity, id="act-1")]
        mock_query.return_value = (mock_activities, None)

        result = await timeline_fn(limit=20, cursor=None)

    mock_query.assert_called_once_with("public", 20, None)
    assert len(result.items) == 1
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_public_posts_feed_calls_correct_team(router):
    """Posts feed should query the 'public' virtual team."""
    posts_fn = _get_endpoint(router, "/public/posts")

    with patch(
        "intentkit.core.public_api.query_post_feed", new_callable=AsyncMock
    ) as mock_query:
        mock_posts = [MagicMock(spec=AgentPostBrief, id="post-1")]
        mock_query.return_value = (mock_posts, "cursor-next")

        result = await posts_fn(limit=10, cursor=None)

    mock_query.assert_called_once_with("public", 10, None)
    assert len(result.items) == 1
    assert result.next_cursor == "cursor-next"


@pytest.mark.asyncio
async def test_public_timeline_with_cursor(router):
    """Timeline should forward cursor for pagination."""
    timeline_fn = _get_endpoint(router, "/public/timeline")

    with patch(
        "intentkit.core.public_api.query_activity_feed", new_callable=AsyncMock
    ) as mock_query:
        mock_query.return_value = ([], None)
        await timeline_fn(limit=50, cursor="2026-03-30T00:00:00|act-1")

    mock_query.assert_called_once_with("public", 50, "2026-03-30T00:00:00|act-1")


# ---- /public/share-links/{id} tests ----


@pytest.mark.asyncio
async def test_get_share_link_returns_view_and_increments_counter(router):
    """Public share endpoint returns the view and bumps the view counter."""
    from intentkit.models.share_link import ShareLinkTargetType, ShareLinkView

    get_fn = _get_endpoint(router, "/public/share-links/{share_link_id}")

    expected_view = ShareLinkView(
        id="sl-1",
        target_type=ShareLinkTargetType.POST,
        expires_at=datetime.now(),
    )
    with (
        patch(
            "intentkit.core.public_api.get_shared_view", new_callable=AsyncMock
        ) as mock_get,
        patch(
            "intentkit.core.public_api.increment_share_link_view_count",
            new_callable=AsyncMock,
        ) as mock_inc,
    ):
        mock_get.return_value = expected_view
        result = await get_fn(share_link_id="sl-1")

    assert result is expected_view
    mock_get.assert_awaited_once_with("sl-1")
    mock_inc.assert_awaited_once_with("sl-1")


@pytest.mark.asyncio
async def test_get_share_link_404_skips_counter(router):
    """404 path must not bump the view counter."""
    from intentkit.utils.error import IntentKitAPIError

    get_fn = _get_endpoint(router, "/public/share-links/{share_link_id}")

    with (
        patch(
            "intentkit.core.public_api.get_shared_view", new_callable=AsyncMock
        ) as mock_get,
        patch(
            "intentkit.core.public_api.increment_share_link_view_count",
            new_callable=AsyncMock,
        ) as mock_inc,
    ):
        mock_get.return_value = None
        with pytest.raises(IntentKitAPIError) as exc:
            await get_fn(share_link_id="sl-gone")

    assert exc.value.status_code == 404
    mock_inc.assert_not_awaited()
