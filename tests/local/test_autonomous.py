import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intentkit.models.agent import Agent, AgentAutonomous
from intentkit.models.agent_data import AgentData

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
async def test_add_autonomous(client, mock_agent, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get_agent(agent_id):
        return mock_agent

    async def mock_patch_agent(agent_id, update_data, owner):
        # Simulate adding the task
        new_tasks = update_data.autonomous
        # In the real code we rely on patch_agent returning the updated agent.
        # We need to return an agent that has the new task.

        mock_agent.autonomous = new_tasks
        return mock_agent, AgentData(id=agent_id)

    monkeypatch.setattr(autonomous_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(autonomous_module, "patch_agent", mock_patch_agent)

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
async def test_update_autonomous(client, mock_agent, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get_agent(agent_id):
        return mock_agent

    async def mock_patch_agent(agent_id, update_data, owner):
        mock_agent.autonomous = update_data.autonomous
        return mock_agent, AgentData(id=agent_id)

    monkeypatch.setattr(autonomous_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(autonomous_module, "patch_agent", mock_patch_agent)

    payload = {"name": "Updated Task", "enabled": False}

    response = client.patch("/agents/test-agent/autonomous/task-1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task-1"
    assert data["name"] == "Updated Task"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_autonomous(client, mock_agent, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_get_agent(agent_id):
        return mock_agent

    async def mock_patch_agent(agent_id, update_data, owner):
        mock_agent.autonomous = update_data.autonomous
        return mock_agent, AgentData(id=agent_id)

    monkeypatch.setattr(autonomous_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(autonomous_module, "patch_agent", mock_patch_agent)

    response = client.delete("/agents/test-agent/autonomous/task-1")
    assert response.status_code == 204

    # Verify it's gone from the agent (simulated by our mock interaction, mostly ensuring 204 returned)
