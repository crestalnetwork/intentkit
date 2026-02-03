import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intentkit.models.agent import Agent, AgentAutonomous

from app.local.autonomous import autonomous_router


# Create a test app with the autonomous router
def create_test_app():
    app = FastAPI()
    app.include_router(autonomous_router)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


@pytest.fixture
def mock_agent():
    agent = Agent.model_construct(
        id="test-agent",
        owner="user",
        autonomous=[
            AgentAutonomous(
                id="task-1",
                name="Task 1",
                cron="0 * * * *",
                prompt="Do something",
                enabled=True,
                status="waiting",
                minutes=None,
                next_run_time=None,
            )
        ],
    )
    return agent


@pytest.fixture
def mock_task():
    return AgentAutonomous(
        id="new-task-id",
        name="New Task",
        cron="*/5 * * * *",
        prompt="New prompt",
        enabled=True,
        status="waiting",
        minutes=None,
        next_run_time=None,
    )


@pytest.mark.asyncio
async def test_list_autonomous(client, mock_agent, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get_agent(agent_id):
        if agent_id == "test-agent":
            return mock_agent
        return None

    monkeypatch.setattr(autonomous_module, "get_agent", mock_get_agent)

    response = client.get("/agents/test-agent/autonomous")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "task-1"
    assert data[0]["chat_id"] == "autonomous-task-1"


@pytest.mark.asyncio
async def test_add_autonomous(client, mock_task, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_add_autonomous_task(agent_id, task_request):
        # Simulate adding the task and returning the created task
        return mock_task

    monkeypatch.setattr(
        autonomous_module, "add_autonomous_task", mock_add_autonomous_task
    )

    payload = {
        "name": "New Task",
        "cron": "*/5 * * * *",
        "prompt": "New prompt",
        "enabled": True,
    }

    response = client.post("/agents/test-agent/autonomous", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Task"
    assert data["cron"] == "*/5 * * * *"
    assert data["chat_id"].startswith("autonomous-")


@pytest.mark.asyncio
async def test_update_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    updated_task = AgentAutonomous(
        id="task-1",
        name="Updated Task",
        cron="0 * * * *",
        prompt="Do something",
        enabled=False,
        status=None,
        minutes=None,
        next_run_time=None,
    )

    async def mock_update_autonomous_task(agent_id, task_id, task_update):
        return updated_task

    monkeypatch.setattr(
        autonomous_module, "update_autonomous_task", mock_update_autonomous_task
    )

    payload = {"name": "Updated Task", "enabled": False}

    response = client.patch("/agents/test-agent/autonomous/task-1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task-1"
    assert data["name"] == "Updated Task"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_delete_autonomous_task(agent_id, task_id):
        # Simulate successful deletion
        pass

    monkeypatch.setattr(
        autonomous_module, "delete_autonomous_task", mock_delete_autonomous_task
    )

    response = client.delete("/agents/test-agent/autonomous/task-1")
    assert response.status_code == 204
