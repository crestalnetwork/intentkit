from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intentkit.models.autonomous import (
    AutonomousExecution,
    AutonomousExecutionTrigger,
    AutonomousTask,
    AutonomousTaskStatus,
)
from intentkit.models.chat import AuthorType, ChatMessage
from intentkit.utils.error import IntentKitAPIError, intentkit_api_error_handler

from app.local.autonomous import autonomous_router
from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID


# Create a test app with the autonomous router
def create_test_app():
    app = FastAPI()
    app.include_router(autonomous_router)
    _ = app.exception_handler(IntentKitAPIError)(intentkit_api_error_handler)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


@pytest.fixture
def mock_task():
    return AutonomousTask(
        id="new-task-id",
        team_id=LEAD_TEAM_ID,
        name="New Task",
        cron="*/5 * * * *",
        prompt="New prompt",
        enabled=True,
        status=AutonomousTaskStatus.WAITING,
        next_run_time=None,
    )


@pytest.mark.asyncio
async def test_list_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_list(team_id):
        assert team_id == LEAD_TEAM_ID
        return [
            AutonomousTask(
                id="task-1",
                team_id=LEAD_TEAM_ID,
                name="Task 1",
                cron="0 * * * *",
                prompt="Do something",
                enabled=True,
                status=AutonomousTaskStatus.WAITING,
            )
        ]

    monkeypatch.setattr(autonomous_module, "list_team_autonomous_tasks", mock_list)

    response = client.get("/autonomous")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "task-1"
    assert data[0]["chat_id"] == "autonomous-task-1"
    # No target agent pinned: nothing to resolve
    assert data[0]["target_agent"] is None


@pytest.mark.asyncio
async def test_list_autonomous_attaches_target_agent(client, monkeypatch):
    from intentkit.core.agent.info import AgentInfo

    import app.local.autonomous as autonomous_module

    async def mock_list(team_id):
        return [
            AutonomousTask(
                id="task-1",
                team_id=LEAD_TEAM_ID,
                name="Task 1",
                cron="0 * * * *",
                prompt="Do something",
                enabled=True,
                status=AutonomousTaskStatus.WAITING,
                target_agent_id="agent-x",
            ),
            AutonomousTask(
                id="task-2",
                team_id=LEAD_TEAM_ID,
                name="Task 2",
                cron="0 * * * *",
                prompt="Do something else",
                enabled=True,
                status=AutonomousTaskStatus.WAITING,
                target_agent_id="agent-gone",
            ),
        ]

    async def fake_get_agent_infos(agent_ids):
        ids = set(agent_ids)
        assert ids == {"agent-x", "agent-gone"}
        return {
            "agent-x": AgentInfo(
                id="agent-x", name="Agent X", picture="x.png", slug="agent-x"
            )
        }

    monkeypatch.setattr(autonomous_module, "list_team_autonomous_tasks", mock_list)
    monkeypatch.setattr("app.common.autonomous.get_agent_infos", fake_get_agent_infos)

    response = client.get("/autonomous")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["target_agent"] == {
        "id": "agent-x",
        "name": "Agent X",
        "picture": "x.png",
        "slug": "agent-x",
    }
    # A deleted target agent leaves the id but no display info
    assert data[1]["target_agent_id"] == "agent-gone"
    assert data[1]["target_agent"] is None


@pytest.mark.asyncio
async def test_add_autonomous(client, mock_task, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_add_autonomous_task(team_id, task_request, created_by=None):
        assert team_id == LEAD_TEAM_ID
        assert created_by == LEAD_USER_ID
        return mock_task

    monkeypatch.setattr(
        autonomous_module, "add_autonomous_task", mock_add_autonomous_task
    )

    payload = {
        "name": "New Task",
        "cron": "*/5 * * * *",
        "prompt": "New prompt",
        "enabled": True,
        "target_agent_id": "agent-x",
    }

    response = client.post("/autonomous", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Task"
    assert data["cron"] == "*/5 * * * *"
    assert data["chat_id"].startswith("autonomous-")


@pytest.mark.asyncio
async def test_update_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    updated_task = AutonomousTask(
        id="task-1",
        team_id=LEAD_TEAM_ID,
        name="Updated Task",
        cron="0 * * * *",
        prompt="Do something",
        enabled=False,
        status=None,
        next_run_time=None,
    )

    async def mock_update_autonomous_task(team_id, task_id, task_update):
        assert team_id == LEAD_TEAM_ID
        return updated_task

    monkeypatch.setattr(
        autonomous_module, "update_autonomous_task", mock_update_autonomous_task
    )

    payload = {"name": "Updated Task", "enabled": False}

    response = client.patch("/autonomous/task-1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task-1"
    assert data["name"] == "Updated Task"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_delete_autonomous_task(team_id, task_id):
        assert team_id == LEAD_TEAM_ID

    monkeypatch.setattr(
        autonomous_module, "delete_autonomous_task", mock_delete_autonomous_task
    )

    response = client.delete("/autonomous/task-1")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_autonomous(client, mock_task, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get(team_id, task_id):
        assert team_id == LEAD_TEAM_ID
        assert task_id == "new-task-id"
        return mock_task

    monkeypatch.setattr(autonomous_module, "get_autonomous_task", mock_get)

    response = client.get("/autonomous/new-task-id")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "new-task-id"
    assert data["chat_id"] == "autonomous-new-task-id"


def _mock_execution(**overrides):
    base = {
        "id": "exec-1",
        "task_id": "task-1",
        "team_id": LEAD_TEAM_ID,
        "agent_id": "agent-x",
        "target_agent_id": "agent-x",
        "chat_id": "autonomous-task-1",
        "message_id": "msg-1",
        "started_at": datetime.now(UTC),
    }
    base.update(overrides)
    return AutonomousExecution.model_validate(base)


@pytest.mark.asyncio
async def test_execute_autonomous_runs_in_background(client, mock_task, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get(team_id, task_id):
        return mock_task

    async def mock_fresh_running(task_id):
        return None

    run_calls = {}

    async def mock_run(**kwargs):
        run_calls.update(kwargs)

    monkeypatch.setattr(autonomous_module, "get_autonomous_task", mock_get)
    monkeypatch.setattr(
        autonomous_module, "get_fresh_running_execution", mock_fresh_running
    )
    monkeypatch.setattr(autonomous_module, "run_autonomous_task", mock_run)

    response = client.post("/autonomous/new-task-id/execute")
    assert response.status_code == 202
    # TestClient runs background tasks before returning.
    assert run_calls["task_id"] == "new-task-id"
    assert run_calls["trigger"] == AutonomousExecutionTrigger.MANUAL
    assert run_calls["triggered_by"] == LEAD_USER_ID
    assert run_calls["owner_user_id"] == LEAD_USER_ID


@pytest.mark.asyncio
async def test_execute_autonomous_conflicts_while_running(
    client, mock_task, monkeypatch
):
    import app.local.autonomous as autonomous_module

    async def mock_get(team_id, task_id):
        return mock_task

    async def mock_fresh_running(task_id):
        return _mock_execution()

    monkeypatch.setattr(autonomous_module, "get_autonomous_task", mock_get)
    monkeypatch.setattr(
        autonomous_module, "get_fresh_running_execution", mock_fresh_running
    )

    response = client.post("/autonomous/new-task-id/execute")
    assert response.status_code == 409
    assert response.json()["error"] == "AutonomousTaskRunning"


@pytest.mark.asyncio
async def test_list_executions(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_list(team_id, task_id, *, cursor=None, limit=20):
        assert team_id == LEAD_TEAM_ID
        assert task_id == "task-1"
        return [_mock_execution()], True, "exec-1"

    monkeypatch.setattr(autonomous_module, "list_autonomous_executions", mock_list)

    response = client.get("/autonomous/task-1/executions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "exec-1"
    assert data["data"][0]["status"] == "running"
    assert data["has_more"] is True
    assert data["next_cursor"] == "exec-1"


@pytest.mark.asyncio
async def test_get_execution_messages(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    log = [
        ChatMessage(
            id="msg-1",
            agent_id="agent-x",
            chat_id="autonomous-task-1",
            user_id="user-1",
            author_id="autonomous",
            author_type=AuthorType.TRIGGER,
            reply_to="msg-1",
            message="do work",
            created_at=datetime.now(UTC),
        )
    ]

    async def mock_messages(team_id, task_id, execution_id):
        assert (team_id, task_id, execution_id) == (LEAD_TEAM_ID, "task-1", "exec-1")
        return log

    monkeypatch.setattr(
        autonomous_module, "get_autonomous_execution_messages", mock_messages
    )

    response = client.get("/autonomous/task-1/executions/exec-1/messages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "msg-1"


@pytest.mark.asyncio
async def test_legacy_migration_failure_is_contained_and_alerts_once(monkeypatch):
    import app.autonomous as autonomous_module

    alerts: list[str] = []
    monkeypatch.setattr(autonomous_module, "send_alert", alerts.append)
    monkeypatch.setattr(autonomous_module, "_legacy_migration_alerted", False)
    monkeypatch.setattr(
        "importlib.util.spec_from_file_location",
        lambda *args, **kwargs: None,
    )

    # Must not raise: a failed legacy migration only logs and alerts.
    assert await autonomous_module.run_legacy_autonomous_migration() is False
    # Retries (here: a second failure) don't spam the alert channel.
    assert await autonomous_module.run_legacy_autonomous_migration() is False
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_legacy_migration_failure_survives_failing_alerter(monkeypatch):
    import app.autonomous as autonomous_module

    def broken_alert(message: str) -> None:
        raise RuntimeError("alert transport down")

    monkeypatch.setattr(autonomous_module, "send_alert", broken_alert)
    monkeypatch.setattr(autonomous_module, "_legacy_migration_alerted", False)
    monkeypatch.setattr(
        "importlib.util.spec_from_file_location",
        lambda *args, **kwargs: None,
    )

    # A raising alerter must not escape the containment either.
    assert await autonomous_module.run_legacy_autonomous_migration() is False


@pytest.mark.asyncio
async def test_sweep_waits_for_legacy_migration(monkeypatch):
    import app.autonomous as autonomous_module

    monkeypatch.setattr(autonomous_module, "_legacy_migration_done", False)
    calls = {"migration": 0}

    async def failing_migration() -> bool:
        calls["migration"] += 1
        return False

    monkeypatch.setattr(
        autonomous_module, "run_legacy_autonomous_migration", failing_migration
    )

    def must_not_be_called():
        raise AssertionError("sweep must not touch the DB before migration succeeds")

    monkeypatch.setattr(autonomous_module, "get_session", must_not_be_called)

    # Failed migration -> the sweep retries next time and prunes nothing now.
    await autonomous_module.schedule_agent_autonomous_tasks()
    assert calls["migration"] == 1
    assert autonomous_module._legacy_migration_done is False


@pytest.mark.asyncio
async def test_sweep_runs_migration_once_then_proceeds(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import app.autonomous as autonomous_module

    monkeypatch.setattr(autonomous_module, "_legacy_migration_done", False)
    calls = {"migration": 0}

    async def ok_migration() -> bool:
        calls["migration"] += 1
        return True

    monkeypatch.setattr(
        autonomous_module, "run_legacy_autonomous_migration", ok_migration
    )

    session = MagicMock()
    session.scalars = AsyncMock(return_value=[])
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(autonomous_module, "get_session", lambda: ctx)
    monkeypatch.setattr(autonomous_module.scheduler, "get_jobs", list)

    await autonomous_module.schedule_agent_autonomous_tasks()
    assert autonomous_module._legacy_migration_done is True
    # Once done, later sweeps skip the migration check entirely.
    await autonomous_module.schedule_agent_autonomous_tasks()
    assert calls["migration"] == 1


@pytest.mark.asyncio
async def test_update_autonomous_status_uses_core_update(monkeypatch):
    import app.autonomous as autonomous_module

    called = {"value": False}

    async def mock_update_autonomous_task_status(
        team_id, task_id, status, next_run_time
    ):
        called["value"] = True

    class MockJob:
        def __init__(self):
            self.id = "team-1-task-1"
            self.args = ["team-1", "user", "task-1", "prompt", True, None]
            self.next_run_time = None

    monkeypatch.setattr(
        autonomous_module,
        "update_autonomous_task_status",
        mock_update_autonomous_task_status,
    )
    monkeypatch.setattr(
        autonomous_module.scheduler, "get_job", lambda _job_id: MockJob()
    )

    await autonomous_module.update_autonomous_status(
        "team-1-task-1", AutonomousTaskStatus.RUNNING
    )

    assert called["value"] is True
