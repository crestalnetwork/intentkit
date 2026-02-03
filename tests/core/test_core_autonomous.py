from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.agent.autonomous import (
    AgentAutonomous,
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
    minutes_to_cron,
)


@pytest.mark.asyncio
async def test_add_autonomous_task():
    """Test adding an autonomous task using the core function."""
    from intentkit.core.autonomous import add_autonomous_task

    agent_id = "test-agent-id"
    task_request = AutonomousCreateRequest(
        name="Test Task",
        description="A test task",
        cron="*/5 * * * *",
        prompt="Do something",
        enabled=True,
        has_memory=True,
    )

    # Mock the database session
    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock agent exists and is not archived
        mock_db_agent = MagicMock()
        mock_db_agent.archived_at = None
        mock_db_agent.autonomous = None  # No existing tasks
        mock_session.get = AsyncMock(return_value=mock_db_agent)
        mock_session.commit = AsyncMock()

        result = await add_autonomous_task(agent_id, task_request)

        # Verify the result
        assert result.name == "Test Task"
        assert result.description == "A test task"
        assert result.cron == "*/5 * * * *"
        assert result.prompt == "Do something"
        assert result.enabled is True
        assert result.has_memory is True
        assert result.minutes is None  # minutes should not be set
        assert result.status.value == "waiting"  # Default status for enabled task
        assert result.id is not None  # ID should be auto-generated

        # Verify DB was updated
        mock_session.commit.assert_called_once()
        assert mock_db_agent.autonomous is not None


@pytest.mark.asyncio
async def test_update_autonomous_task():
    """Test updating an autonomous task using the core function."""
    from intentkit.core.autonomous import update_autonomous_task

    agent_id = "test-agent-id"
    task_id = "test-task-id"

    existing_task = AgentAutonomous(
        id=task_id,
        name="Original Task",
        description="Original description",
        cron="*/10 * * * *",
        prompt="Original prompt",
        enabled=True,
        has_memory=True,
        status="waiting",
    )

    update_request = AutonomousUpdateRequest(
        name="Updated Task",
        enabled=False,
    )

    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_db_agent = MagicMock()
        mock_db_agent.archived_at = None
        mock_db_agent.autonomous = [existing_task.model_dump()]
        mock_session.get = AsyncMock(return_value=mock_db_agent)
        mock_session.commit = AsyncMock()

        result = await update_autonomous_task(agent_id, task_id, update_request)

        # Verify updated fields
        assert result.name == "Updated Task"
        assert result.enabled is False
        assert result.status is None  # Should be cleared when disabled

        # Verify unchanged fields
        assert result.cron == "*/10 * * * *"
        assert result.prompt == "Original prompt"
        assert result.description == "Original description"
        assert result.has_memory is True

        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_autonomous_task():
    """Test deleting an autonomous task using the core function."""
    from intentkit.core.autonomous import delete_autonomous_task

    agent_id = "test-agent-id"
    task_id = "test-task-id"

    existing_task = AgentAutonomous(
        id=task_id,
        name="Task to Delete",
        cron="*/5 * * * *",
        prompt="Delete me",
        enabled=False,
    )

    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_db_agent = MagicMock()
        mock_db_agent.archived_at = None
        mock_db_agent.autonomous = [existing_task.model_dump()]
        mock_session.get = AsyncMock(return_value=mock_db_agent)
        mock_session.commit = AsyncMock()

        await delete_autonomous_task(agent_id, task_id)

        # Verify task was removed
        assert mock_db_agent.autonomous == []
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_list_autonomous_tasks():
    """Test listing autonomous tasks using the core function."""
    from intentkit.core.autonomous import list_autonomous_tasks

    agent_id = "test-agent-id"

    task1 = AgentAutonomous(
        id="task-1",
        name="Task 1",
        cron="*/5 * * * *",
        prompt="First task",
        enabled=True,
        status="waiting",
    )
    task2 = AgentAutonomous(
        id="task-2",
        name="Task 2",
        cron="0 * * * *",
        prompt="Second task",
        enabled=False,
    )

    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock the execute result for list_autonomous_tasks which uses session.execute
        mock_result = MagicMock()
        mock_result.first.return_value = (
            [task1.model_dump(), task2.model_dump()],  # autonomous data
            None,  # archived_at
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await list_autonomous_tasks(agent_id)

        assert len(result) == 2
        assert result[0].id == "task-1"
        assert result[0].name == "Task 1"
        assert result[1].id == "task-2"
        assert result[1].name == "Task 2"


def test_autonomous_create_request_no_minutes_field():
    """Verify that AutonomousCreateRequest does not have a minutes field."""
    # This ensures the minutes field is properly deprecated
    req = AutonomousCreateRequest(
        cron="* * * * *",
        prompt="foo",
    )

    # minutes should not be in the model fields
    assert "minutes" not in AutonomousCreateRequest.model_fields

    # Verify default values
    assert req.enabled is False
    assert req.has_memory is True
    assert req.name is None
    assert req.description is None


def test_autonomous_update_request_no_minutes_field():
    """Verify that AutonomousUpdateRequest does not have a minutes field."""
    req = AutonomousUpdateRequest(
        name="Updated",
    )

    # minutes should not be in the model fields
    assert "minutes" not in AutonomousUpdateRequest.model_fields

    # All fields should be optional (None by default)
    assert req.name == "Updated"
    assert req.cron is None
    assert req.prompt is None
    assert req.enabled is None
    assert req.has_memory is None


@pytest.mark.asyncio
async def test_add_autonomous_task_agent_not_found():
    """Test that adding task to non-existent agent raises error."""
    from intentkit.core.autonomous import add_autonomous_task
    from intentkit.utils.error import IntentKitAPIError

    agent_id = "non-existent-agent"
    task_request = AutonomousCreateRequest(
        cron="*/5 * * * *",
        prompt="Do something",
    )

    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Agent not found
        mock_session.get = AsyncMock(return_value=None)

        with pytest.raises(IntentKitAPIError) as exc_info:
            await add_autonomous_task(agent_id, task_request)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_autonomous_task_not_found():
    """Test that deleting non-existent task raises error."""
    from intentkit.core.autonomous import delete_autonomous_task
    from intentkit.utils.error import IntentKitAPIError

    agent_id = "test-agent-id"
    task_id = "non-existent-task"

    with patch("intentkit.core.autonomous.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_db_agent = MagicMock()
        mock_db_agent.archived_at = None
        mock_db_agent.autonomous = []  # No tasks
        mock_session.get = AsyncMock(return_value=mock_db_agent)

        with pytest.raises(IntentKitAPIError) as exc_info:
            await delete_autonomous_task(agent_id, task_id)

        assert exc_info.value.status_code == 404


# Tests for minutes to cron conversion


def test_minutes_to_cron_basic():
    """Test basic minutes to cron conversion."""
    assert minutes_to_cron(5) == "*/5 * * * *"
    assert minutes_to_cron(10) == "*/10 * * * *"
    assert minutes_to_cron(15) == "*/15 * * * *"
    assert minutes_to_cron(30) == "*/30 * * * *"


def test_minutes_to_cron_hourly():
    """Test hourly conversion for >= 60 minutes."""
    assert minutes_to_cron(60) == "0 */1 * * *"
    assert minutes_to_cron(120) == "0 */2 * * *"
    assert minutes_to_cron(180) == "0 */3 * * *"


def test_minutes_to_cron_daily():
    """Test daily conversion for >= 24 hours."""
    assert minutes_to_cron(1440) == "0 0 * * *"  # 24 hours
    assert minutes_to_cron(2880) == "0 0 * * *"  # 48 hours


def test_minutes_to_cron_invalid():
    """Test invalid minutes defaults to 5."""
    assert minutes_to_cron(0) == "*/5 * * * *"
    assert minutes_to_cron(-1) == "*/5 * * * *"


def test_normalize_converts_minutes_to_cron():
    """Test that normalize_status_defaults converts minutes to cron."""
    task = AgentAutonomous(
        id="test-task",
        minutes=10,
        cron=None,
        prompt="Test prompt",
        enabled=True,
    )

    normalized = task.normalize_status_defaults()

    assert normalized.cron == "*/10 * * * *"
    assert normalized.minutes is None  # Should be cleared
    assert normalized.status.value == "waiting"  # Should be set for enabled


def test_normalize_preserves_cron_if_set():
    """Test that normalize_status_defaults does not override existing cron."""
    task = AgentAutonomous(
        id="test-task",
        minutes=10,  # This should be ignored
        cron="0 */2 * * *",  # Existing cron
        prompt="Test prompt",
        enabled=True,
    )

    normalized = task.normalize_status_defaults()

    # cron should be preserved, not converted from minutes
    assert normalized.cron == "0 */2 * * *"
    # minutes should remain (cron was already set)
    assert normalized.minutes == 10
    assert normalized.status.value == "waiting"


def test_normalize_clears_status_when_disabled():
    """Test that normalize_status_defaults clears status when disabled."""
    task = AgentAutonomous(
        id="test-task",
        minutes=15,
        prompt="Test prompt",
        enabled=False,
        status="waiting",
    )

    normalized = task.normalize_status_defaults()

    assert normalized.cron == "*/15 * * * *"
    assert normalized.minutes is None
    assert normalized.status is None  # Cleared because disabled
