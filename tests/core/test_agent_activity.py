import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.core.agent_activity as agent_activity_module
from intentkit.core.agent_activity import (
    create_agent_activity,
    get_agent_activities,
    get_agent_activity,
)
from intentkit.models.agent_activity import (
    AgentActivity,
    AgentActivityCreate,
    AgentActivityTable,
)


@pytest.mark.asyncio
async def test_create_agent_activity(monkeypatch):
    # Mock session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def mock_refresh(obj):
        obj.id = "activity-123"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_cls)

    activity_create = AgentActivityCreate(
        agent_id="agent-1",
        text="Test Activity",
        images=["img1.jpg"],
        video="video.mp4",
        post_id="post-1",
    )

    result = await create_agent_activity(activity_create)

    # Verify session usage
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Verify result
    assert isinstance(result, AgentActivity)
    assert result.agent_id == "agent-1"
    assert result.text == "Test Activity"
    assert result.images == ["img1.jpg"]
    assert result.video == "video.mp4"
    assert result.post_id == "post-1"
    assert result.id == "activity-123"


@pytest.mark.asyncio
async def test_get_agent_activity_cache_hit(monkeypatch):
    activity_id = "activity-123"
    cached_data = {
        "id": activity_id,
        "agent_id": "agent-1",
        "text": "Cached Activity",
        "images": [],
        "video": None,
        "post_id": None,
        "created_at": datetime.now().isoformat(),
    }

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(cached_data)

    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    result = await get_agent_activity(activity_id)

    # Verify usage
    mock_redis.get.assert_called_with(f"intentkit:agent_activity:{activity_id}")

    assert isinstance(result, AgentActivity)
    assert result.id == activity_id
    assert result.text == "Cached Activity"


@pytest.mark.asyncio
async def test_get_agent_activity_cache_miss_db_hit(monkeypatch):
    activity_id = "activity-123"

    # Mock Redis (Miss then Set)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    # Mock DB Result
    db_activity = AgentActivityTable(
        id=activity_id,
        agent_id="agent-1",
        text="DB Activity",
        images=None,
        video=None,
        post_id=None,
        created_at=datetime.now(),
    )

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_activity
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activity(activity_id)

    # Verify
    mock_redis.get.assert_called_once()
    mock_session.execute.assert_called_once()
    mock_redis.set.assert_called_once()

    assert isinstance(result, AgentActivity)
    assert result.text == "DB Activity"


@pytest.mark.asyncio
async def test_get_agent_activity_db_miss(monkeypatch):
    activity_id = "activity-missing"

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activity(activity_id)

    assert result is None
    assert not mock_redis.set.called


@pytest.mark.asyncio
async def test_get_agent_activities(monkeypatch):
    agent_id = "agent-1"

    # Create mock db activities
    db_activities = [
        AgentActivityTable(
            id=f"activity-{i}",
            agent_id=agent_id,
            text=f"Activity {i}",
            images=None,
            video=None,
            post_id=None,
            created_at=datetime.now(),
        )
        for i in range(3)
    ]

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = db_activities
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activities(agent_id, limit=10)

    # Verify
    mock_session.execute.assert_called_once()
    assert len(result) == 3
    for i, activity in enumerate(result):
        assert isinstance(activity, AgentActivity)
        assert activity.id == f"activity-{i}"
        assert activity.text == f"Activity {i}"


@pytest.mark.asyncio
async def test_get_agent_activities_empty(monkeypatch):
    agent_id = "agent-no-activities"

    # Mock Session with empty result
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activities(agent_id)

    assert result == []
