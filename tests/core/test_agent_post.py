import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.core.agent_post as agent_post_module
from intentkit.core.agent_post import create_agent_post, get_agent_post
from intentkit.models.agent_post import AgentPost, AgentPostCreate, AgentPostTable


@pytest.mark.asyncio
async def test_create_agent_post(monkeypatch):
    # Mock session
    mock_session = AsyncMock()
    # add is sync
    mock_session.add = MagicMock()

    # refresh side effect to simulate DB defaults
    async def mock_refresh(obj):
        obj.id = "post-123"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(agent_post_module, "get_session", lambda: mock_session_cls)

    post_create = AgentPostCreate(
        agent_id="agent-1",
        agent_name="Test Agent",
        agent_picture="https://example.com/avatar.png",
        title="Test Post",
        markdown="Content",
        cover="image.jpg",
        tags=[],
    )

    result = await create_agent_post(post_create)

    # Verify session usage
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Verify result
    assert isinstance(result, AgentPost)
    assert result.agent_id == "agent-1"
    assert result.agent_name == "Test Agent"
    assert result.agent_picture == "https://example.com/avatar.png"
    assert result.title == "Test Post"
    assert result.id == "post-123"


@pytest.mark.asyncio
async def test_get_agent_post_cache_hit(monkeypatch):
    post_id = "post-123"
    cached_data = {
        "id": post_id,
        "agent_id": "agent-1",
        "agent_name": "Cached Agent",
        "agent_picture": "https://example.com/cached.png",
        "title": "Cached Post",
        "markdown": "Content",
        "cover": None,
        "created_at": datetime.now().isoformat(),
        "tags": [],
    }

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(cached_data)

    monkeypatch.setattr(agent_post_module, "get_redis", lambda: mock_redis)

    # Mock Session (should not be called)
    mock_session = AsyncMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    monkeypatch.setattr(agent_post_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_post(post_id)

    # Verify usage
    mock_redis.get.assert_called_with(f"intentkit:agent_post:{post_id}")
    assert not mock_session.execute.called

    assert isinstance(result, AgentPost)
    assert result.id == post_id
    assert result.agent_name == "Cached Agent"
    assert result.agent_picture == "https://example.com/cached.png"
    assert result.title == "Cached Post"


@pytest.mark.asyncio
async def test_get_agent_post_cache_miss_db_hit(monkeypatch):
    post_id = "post-123"

    # Mock Redis (Miss then Set)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_post_module, "get_redis", lambda: mock_redis)

    # Mock DB Result
    db_post = AgentPostTable(
        id=post_id,
        agent_id="agent-1",
        agent_name="DB Agent",
        agent_picture="https://example.com/db.png",
        title="DB Post",
        markdown="Content",
        cover=None,
        created_at=datetime.now(),
        tags=[],
    )

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_post
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_post_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_post(post_id)

    # Verify
    mock_redis.get.assert_called_once()
    mock_session.execute.assert_called_once()
    mock_redis.set.assert_called_once()

    assert isinstance(result, AgentPost)
    assert result.agent_name == "DB Agent"
    assert result.agent_picture == "https://example.com/db.png"
    assert result.title == "DB Post"


@pytest.mark.asyncio
async def test_get_agent_post_db_miss(monkeypatch):
    post_id = "post-missing"

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_post_module, "get_redis", lambda: mock_redis)

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_post_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_post(post_id)

    assert result is None
    assert not mock_redis.set.called


@pytest.mark.asyncio
async def test_create_agent_post_with_none_picture(monkeypatch):
    """Test creating post when agent_picture is None."""
    # Mock session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def mock_refresh(obj):
        obj.id = "post-456"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(agent_post_module, "get_session", lambda: mock_session_cls)

    # Create post without agent_picture (should default to None)
    post_create = AgentPostCreate(
        agent_id="agent-1",
        agent_name="Test Agent",
        title="Test Post",
        markdown="Content",
        tags=[],
    )

    result = await create_agent_post(post_create)

    # Verify result
    assert isinstance(result, AgentPost)
    assert result.agent_id == "agent-1"
    assert result.agent_name == "Test Agent"
    assert result.agent_picture is None
    assert result.title == "Test Post"
