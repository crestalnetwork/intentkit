"""Tests for Content API endpoints (activities and posts)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from intentkit.models.agent_activity import AgentActivityTable
from intentkit.models.agent_post import AgentPostTable

from app.local.content import content_router


# Create a test app with only the content router
def create_test_app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(content_router)
    return app


@pytest.fixture
def test_client():
    return TestClient(create_test_app())


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    mock_session = AsyncMock()
    return mock_session


@pytest.fixture
def sample_activities():
    """Sample activity data for tests."""
    now = datetime.now()
    return [
        AgentActivityTable(
            id="activity-1",
            agent_id="agent-1",
            text="First activity",
            images=["img1.jpg"],
            video=None,
            post_id=None,
            created_at=now,
        ),
        AgentActivityTable(
            id="activity-2",
            agent_id="agent-1",
            text="Second activity",
            images=None,
            video="video.mp4",
            post_id="post-1",
            created_at=now,
        ),
        AgentActivityTable(
            id="activity-3",
            agent_id="agent-2",
            text="Third activity from agent 2",
            images=None,
            video=None,
            post_id=None,
            created_at=now,
        ),
    ]


@pytest.fixture
def sample_posts():
    """Sample post data for tests."""
    now = datetime.now()
    return [
        AgentPostTable(
            id="post-1",
            agent_id="agent-1",
            agent_name="Agent 1",
            title="First Post Title",
            cover="cover1.jpg",
            markdown="A" * 600,  # Content longer than 500 chars
            created_at=now,
        ),
        AgentPostTable(
            id="post-2",
            agent_id="agent-1",
            agent_name="Agent 1",
            title="Second Post Title",
            cover=None,
            markdown="Short content",
            created_at=now,
        ),
        AgentPostTable(
            id="post-3",
            agent_id="agent-2",
            agent_name="Agent 2",
            title="Post from Agent 2",
            cover="cover3.jpg",
            markdown="Content from agent 2",
            created_at=now,
        ),
    ]


@pytest.mark.asyncio
async def test_get_all_activities(monkeypatch, sample_activities):
    """Test GET /activities returns all activities."""
    import app.local.content as content_module

    # Mock db session
    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = sample_activities
    mock_session.scalars.return_value = mock_scalars

    async def mock_get_db():
        return mock_session

    monkeypatch.setattr(content_module, "get_db", lambda: mock_get_db())

    # Call endpoint directly
    result = await content_module.get_all_activities(db=mock_session)

    assert len(result) == 3
    assert result[0].id == "activity-1"
    assert result[1].text == "Second activity"


@pytest.mark.asyncio
async def test_get_agent_activities(monkeypatch, sample_activities):
    """Test GET /agents/{agent_id}/activities returns filtered activities."""
    import app.local.content as content_module

    # Filter only agent-1 activities
    agent1_activities = [a for a in sample_activities if a.agent_id == "agent-1"]

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = agent1_activities
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_agent_activities(
        agent_id="agent-1", db=mock_session
    )

    assert len(result) == 2
    assert all(a.agent_id == "agent-1" for a in result)


@pytest.mark.asyncio
async def test_get_all_posts_truncates_content(monkeypatch, sample_posts):
    """Test GET /posts returns brief posts with truncated content."""
    import app.local.content as content_module

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = sample_posts
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_all_posts(db=mock_session)

    assert len(result) == 3
    # First post has 600 char content, should be truncated to 500
    assert len(result[0].excerpt or "") == 500
    # Second post has short content, should not be truncated
    assert result[1].excerpt == "Short content"


@pytest.mark.asyncio
async def test_get_agent_posts(monkeypatch, sample_posts):
    """Test GET /agents/{agent_id}/posts returns filtered posts."""
    import app.local.content as content_module

    agent1_posts = [p for p in sample_posts if p.agent_id == "agent-1"]

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = agent1_posts
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_agent_posts(agent_id="agent-1", db=mock_session)

    assert len(result) == 2
    assert all(p.agent_id == "agent-1" for p in result)


@pytest.mark.asyncio
async def test_get_post_full_content(monkeypatch, sample_posts):
    """Test GET /posts/{post_id} returns full post content."""
    import app.local.content as content_module

    post = sample_posts[0]

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = post
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_post(post_id="post-1", db=mock_session)

    assert result.id == "post-1"
    assert len(result.markdown) == 600  # Full content, not truncated


@pytest.mark.asyncio
async def test_get_post_not_found(monkeypatch):
    """Test GET /posts/{post_id} returns 404 for non-existent post."""
    from intentkit.utils.error import IntentKitAPIError

    import app.local.content as content_module

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_session.scalars.return_value = mock_scalars

    with pytest.raises(IntentKitAPIError) as exc_info:
        await content_module.get_post(post_id="nonexistent", db=mock_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "NotFound"


@pytest.mark.asyncio
async def test_get_activities_empty_result(monkeypatch):
    """Test GET /activities with no activities returns empty list."""
    import app.local.content as content_module

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_all_activities(db=mock_session)

    assert result == []


@pytest.mark.asyncio
async def test_get_posts_empty_result(monkeypatch):
    """Test GET /posts with no posts returns empty list."""
    import app.local.content as content_module

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_session.scalars.return_value = mock_scalars

    result = await content_module.get_all_posts(db=mock_session)

    assert result == []
