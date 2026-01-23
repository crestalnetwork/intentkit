import json
from datetime import UTC, datetime

from intentkit.models.agent import AgentAutonomous, AgentAutonomousStatus


class TestAgentAutonomousJsonSerialization:
    """Tests for AgentAutonomous JSON serialization compatibility."""

    def test_next_run_time_serializes_to_iso_string(self):
        """Verify that next_run_time datetime is serialized to ISO format string."""
        now = datetime.now(UTC)
        task = AgentAutonomous(
            id="test123",
            name="Test Task",
            prompt="Test prompt",
            enabled=True,
            status=AgentAutonomousStatus.WAITING,
            next_run_time=now,
        )

        data = task.model_dump()

        assert isinstance(data["next_run_time"], str)
        assert data["next_run_time"] == now.isoformat()

    def test_next_run_time_none_serializes_to_none(self):
        """Verify that None next_run_time remains None after serialization."""
        task = AgentAutonomous(
            id="test123",
            name="Test Task",
            prompt="Test prompt",
            enabled=False,
            next_run_time=None,
        )

        data = task.model_dump()

        assert data["next_run_time"] is None

    def test_model_dump_is_json_serializable(self):
        """Verify that model_dump output can be serialized with standard json.dumps.

        This is critical for SQLAlchemy JSONB storage which uses json.dumps internally.
        """
        task = AgentAutonomous(
            id="test123",
            name="Test Task",
            prompt="Test prompt",
            enabled=True,
            status=AgentAutonomousStatus.WAITING,
            next_run_time=datetime.now(UTC),
        )

        data = task.model_dump()

        # This should not raise TypeError: Object of type datetime is not JSON serializable
        json_str = json.dumps(data)

        assert isinstance(json_str, str)
        # Verify it's valid JSON by parsing it back
        parsed = json.loads(json_str)
        assert parsed["id"] == "test123"
        assert parsed["name"] == "Test Task"
        assert parsed["status"] == "waiting"
        assert isinstance(parsed["next_run_time"], str)

    def test_list_of_autonomous_tasks_is_json_serializable(self):
        """Verify that a list of AgentAutonomous can be serialized.

        This simulates the Agent.autonomous field which is list[AgentAutonomous].
        """
        tasks = [
            AgentAutonomous(
                id="task1",
                name="Task 1",
                prompt="Prompt 1",
                enabled=True,
                status=AgentAutonomousStatus.WAITING,
                next_run_time=datetime.now(UTC),
            ),
            AgentAutonomous(
                id="task2",
                name="Task 2",
                prompt="Prompt 2",
                enabled=True,
                status=AgentAutonomousStatus.RUNNING,
                next_run_time=datetime.now(UTC),
            ),
        ]

        data = [task.model_dump() for task in tasks]

        # This should not raise TypeError
        json_str = json.dumps(data)

        parsed = json.loads(json_str)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "task1"
        assert parsed[1]["id"] == "task2"

    def test_status_enum_serializes_to_string(self):
        """Verify that AgentAutonomousStatus enum serializes to string value."""
        task = AgentAutonomous(
            id="test123",
            prompt="Test prompt",
            enabled=True,
            status=AgentAutonomousStatus.ERROR,
        )

        data = task.model_dump()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed["status"] == "error"


class TestAgentAutonomousStatusDefaults:
    """Tests for AgentAutonomous status normalization logic."""

    def test_normalize_clears_status_when_disabled(self):
        """Verify status and next_run_time are cleared when task is disabled."""
        task = AgentAutonomous(
            id="test123",
            prompt="Test prompt",
            enabled=False,
            status=AgentAutonomousStatus.RUNNING,
            next_run_time=datetime.now(UTC),
        )

        normalized = task.normalize_status_defaults()

        assert normalized.status is None
        assert normalized.next_run_time is None

    def test_normalize_sets_waiting_when_enabled_without_status(self):
        """Verify status is set to WAITING when task is enabled but has no status."""
        task = AgentAutonomous(
            id="test123",
            prompt="Test prompt",
            enabled=True,
            status=None,
        )

        normalized = task.normalize_status_defaults()

        assert normalized.status == AgentAutonomousStatus.WAITING

    def test_normalize_preserves_existing_status_when_enabled(self):
        """Verify existing status is preserved when task is enabled."""
        task = AgentAutonomous(
            id="test123",
            prompt="Test prompt",
            enabled=True,
            status=AgentAutonomousStatus.RUNNING,
        )

        normalized = task.normalize_status_defaults()

        assert normalized.status == AgentAutonomousStatus.RUNNING
