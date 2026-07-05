"""Unit tests for the standalone (team-owned) autonomous task model."""

import pytest

from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousTask,
    AutonomousTaskStatus,
    AutonomousUpdateRequest,
    minutes_to_cron,
    validate_cron_schedule,
)
from intentkit.utils.error import IntentKitAPIError


def test_minutes_to_cron_basic():
    assert minutes_to_cron(5) == "*/5 * * * *"
    assert minutes_to_cron(120) == "0 */2 * * *"
    assert minutes_to_cron(60 * 24 * 3) == "0 0 * * *"


def test_create_request_carries_team_targeting_fields():
    req = AutonomousCreateRequest(
        cron="*/5 * * * *",
        prompt="do work",
        target_agent_id="agent-abc",
    )
    assert req.target_agent_id == "agent-abc"
    assert req.enabled is True


def test_update_request_target_agent_id_optional():
    req = AutonomousUpdateRequest(target_agent_id="agent-xyz")
    assert req.target_agent_id == "agent-xyz"
    # everything else stays unset/None
    dumped = req.model_dump(exclude_unset=True)
    assert dumped == {"target_agent_id": "agent-xyz"}


def test_task_belongs_to_team():
    # model_validate exercises the id default_factory (auto-generated XID).
    task = AutonomousTask.model_validate(
        {"team_id": "team-1", "cron": "*/5 * * * *", "prompt": "do work"}
    )
    assert task.team_id == "team-1"
    assert task.target_agent_id is None
    assert task.id  # auto-generated XID


def test_normalize_disabled_clears_runtime_state():
    task = AutonomousTask(
        id="t1",
        team_id="team-1",
        cron="*/5 * * * *",
        prompt="p",
        enabled=False,
        status=AutonomousTaskStatus.RUNNING,
    )
    normalized = task.normalize_status_defaults()
    assert normalized.status is None
    assert normalized.next_run_time is None


def test_normalize_enabled_defaults_to_waiting():
    task = AutonomousTask(
        id="t1",
        team_id="team-1",
        cron="*/5 * * * *",
        prompt="p",
        enabled=True,
        status=None,
    )
    normalized = task.normalize_status_defaults()
    assert normalized.status == AutonomousTaskStatus.WAITING


def test_validate_cron_schedule_accepts_valid():
    # Should not raise
    validate_cron_schedule("*/5 * * * *")
    validate_cron_schedule("0 9 * * *")
    validate_cron_schedule("0 */2 * * *")


@pytest.mark.parametrize(
    "cron",
    [
        "* * * * *",  # every minute
        "*/2 * * * *",  # every 2 minutes
        "0,30 * * * *",  # twice an hour with wildcard hour is fine actually -> keep below 5? handled
    ],
)
def test_validate_cron_schedule_rejects_too_frequent(cron):
    with pytest.raises(IntentKitAPIError):
        validate_cron_schedule(cron)


def test_validate_cron_schedule_rejects_bad_format():
    with pytest.raises(IntentKitAPIError):
        validate_cron_schedule("not a cron")


def test_next_run_time_serializes_to_iso_string():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    task = AutonomousTask(
        id="t1",
        team_id="team-1",
        cron="*/5 * * * *",
        prompt="p",
        next_run_time=now,
    )
    data = task.model_dump()
    assert isinstance(data["next_run_time"], str)
    assert data["next_run_time"] == now.isoformat()


def test_model_dump_is_json_serializable():
    import json
    from datetime import UTC, datetime

    task = AutonomousTask(
        id="t1",
        team_id="team-1",
        cron="*/5 * * * *",
        prompt="p",
        status=AutonomousTaskStatus.WAITING,
        next_run_time=datetime.now(UTC),
    )
    # Must not raise: datetime is serialized to an ISO string.
    parsed = json.loads(json.dumps(task.model_dump()))
    assert parsed["status"] == "waiting"
    assert parsed["team_id"] == "team-1"
    assert isinstance(parsed["next_run_time"], str)


def test_status_enum_serializes_to_string():
    import json

    task = AutonomousTask(
        id="t1",
        team_id="team-1",
        cron="*/5 * * * *",
        prompt="p",
        status=AutonomousTaskStatus.ERROR,
    )
    parsed = json.loads(json.dumps(task.model_dump()))
    assert parsed["status"] == "error"


def test_execution_defaults():
    from intentkit.models.autonomous import (
        AutonomousExecution,
        AutonomousExecutionStatus,
        AutonomousExecutionTrigger,
    )

    execution = AutonomousExecution.model_validate(
        {
            "task_id": "task-1",
            "team_id": "team-1",
            "agent_id": "team-team-1",
            "chat_id": "autonomous-task-1",
            "message_id": "msg-1",
        }
    )
    assert execution.id  # auto-generated XID
    assert execution.status == AutonomousExecutionStatus.RUNNING
    assert execution.trigger == AutonomousExecutionTrigger.CRON
    assert execution.triggered_by is None
    assert execution.input_tokens == 0
    assert execution.credit_cost is None
    assert execution.finished_at is None


def test_execution_coerces_db_string_enums():
    from intentkit.models.autonomous import (
        AutonomousExecution,
        AutonomousExecutionStatus,
        AutonomousExecutionTrigger,
    )

    # Rows store enums as plain strings; validation must coerce them back.
    execution = AutonomousExecution.model_validate(
        {
            "id": "exec-1",
            "task_id": "task-1",
            "team_id": "team-1",
            "agent_id": "agent-x",
            "chat_id": "autonomous-task-1",
            "message_id": "msg-1",
            "trigger": "manual",
            "status": "error",
            "error": "interrupted",
        }
    )
    assert execution.trigger == AutonomousExecutionTrigger.MANUAL
    assert execution.status == AutonomousExecutionStatus.ERROR
    assert execution.error == "interrupted"
