"""
BDD Tests: Agent Autonomous Task Management

Feature: Autonomous Task Lifecycle
As an IntentKit operator, I want to manage autonomous tasks on agents
so that agents can execute scheduled actions independently.
"""

from datetime import datetime, timezone

import pytest

from intentkit.core.agent import create_agent
from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    list_autonomous_tasks,
    update_autonomous_task,
    update_autonomous_task_status,
)
from intentkit.models.agent import AgentCreate
from intentkit.models.agent.autonomous import (
    AgentAutonomousStatus,
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
)
from intentkit.utils.error import IntentKitAPIError

# Use session-scoped event loop to share DB connections across tests
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_add_autonomous_task_to_agent():
    """
    Scenario: Add an Autonomous Task to an Agent

    Given a deployed agent with `id=auto-agent-1`
    When I call `add_autonomous_task` with a cron schedule and prompt
    Then a task is persisted with correct fields
    And the task has an auto-generated `id`
    And the task `status` is `waiting` because it is enabled
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-1", name="Autonomous Agent 1")
    await create_agent(agent_data)

    # When
    task_request = AutonomousCreateRequest(
        name="Hourly Check",
        description="Check status every hour",
        cron="0 * * * *",
        prompt="Check the system status and report.",
        enabled=True,
        has_memory=True,
    )
    task = await add_autonomous_task("auto-agent-1", task_request)

    # Then
    assert task.id is not None
    assert len(task.id) > 0
    assert task.name == "Hourly Check"
    assert task.description == "Check status every hour"
    assert task.cron == "0 * * * *"
    assert task.prompt == "Check the system status and report."
    assert task.enabled is True
    assert task.has_memory is True
    assert task.status == AgentAutonomousStatus.WAITING


@pytest.mark.bdd
async def test_list_autonomous_tasks():
    """
    Scenario: List Autonomous Tasks for an Agent

    Given a deployed agent with `id=auto-agent-2` that has two autonomous tasks
    When I call `list_autonomous_tasks`
    Then both tasks are returned
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-2", name="Autonomous Agent 2")
    await create_agent(agent_data)

    task1 = AutonomousCreateRequest(
        name="Task Alpha",
        cron="*/5 * * * *",
        prompt="Do alpha work",
        enabled=True,
    )
    task2 = AutonomousCreateRequest(
        name="Task Beta",
        cron="*/10 * * * *",
        prompt="Do beta work",
        enabled=False,
    )
    await add_autonomous_task("auto-agent-2", task1)
    await add_autonomous_task("auto-agent-2", task2)

    # When
    tasks = await list_autonomous_tasks("auto-agent-2")

    # Then
    assert len(tasks) == 2
    names = {t.name for t in tasks}
    assert names == {"Task Alpha", "Task Beta"}


@pytest.mark.bdd
async def test_update_autonomous_task_partial():
    """
    Scenario: Update Autonomous Task with Partial Fields

    Given a deployed agent with an autonomous task
    When I call `update_autonomous_task` with only `name` updated
    Then the task's `name` is updated
    And other fields remain unchanged
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-3", name="Autonomous Agent 3")
    await create_agent(agent_data)

    created = await add_autonomous_task(
        "auto-agent-3",
        AutonomousCreateRequest(
            name="Original Name",
            description="Original Description",
            cron="*/15 * * * *",
            prompt="Original prompt",
            enabled=True,
            has_memory=True,
        ),
    )

    # When
    update = AutonomousUpdateRequest(name="Updated Name")
    updated = await update_autonomous_task("auto-agent-3", created.id, update)

    # Then
    assert updated.name == "Updated Name"
    assert updated.description == "Original Description"
    assert updated.cron == "*/15 * * * *"
    assert updated.prompt == "Original prompt"
    assert updated.enabled is True
    assert updated.has_memory is True


@pytest.mark.bdd
async def test_delete_autonomous_task():
    """
    Scenario: Delete an Autonomous Task

    Given a deployed agent with one autonomous task
    When I call `delete_autonomous_task` with the task's ID
    Then the task is removed
    And `list_autonomous_tasks` returns an empty list
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-4", name="Autonomous Agent 4")
    await create_agent(agent_data)

    created = await add_autonomous_task(
        "auto-agent-4",
        AutonomousCreateRequest(
            name="Deletable Task",
            cron="*/5 * * * *",
            prompt="To be deleted",
        ),
    )

    # When
    await delete_autonomous_task("auto-agent-4", created.id)

    # Then
    tasks = await list_autonomous_tasks("auto-agent-4")
    assert len(tasks) == 0


@pytest.mark.bdd
async def test_add_task_to_nonexistent_agent_fails():
    """
    Scenario: Add Task to Non-Existent Agent Fails

    Given no agent with `id=no-such-agent`
    When I call `add_autonomous_task` with `agent_id=no-such-agent`
    Then an `IntentKitAPIError` with `status_code=404` is raised
    """
    task_request = AutonomousCreateRequest(
        cron="*/5 * * * *",
        prompt="This should fail",
    )

    with pytest.raises(IntentKitAPIError) as exc_info:
        await add_autonomous_task("no-such-agent", task_request)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "AgentNotFound"


@pytest.mark.bdd
async def test_delete_nonexistent_task_fails():
    """
    Scenario: Delete Non-Existent Task Fails

    Given a deployed agent with `id=auto-agent-5` and no tasks
    When I call `delete_autonomous_task` with a non-existent task_id
    Then an `IntentKitAPIError` with `status_code=404` and `key=TaskNotFound` is raised
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-5", name="Autonomous Agent 5")
    await create_agent(agent_data)

    # When/Then
    with pytest.raises(IntentKitAPIError) as exc_info:
        await delete_autonomous_task("auto-agent-5", "nonexistent-task")

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "TaskNotFound"


@pytest.mark.bdd
async def test_operations_on_archived_agent_fail():
    """
    Scenario: Autonomous Operations on Archived Agent Fail

    Given a deployed agent that has been archived
    When I call `list_autonomous_tasks` or `add_autonomous_task`
    Then an `IntentKitAPIError` with `status_code=400` and `key=AgentNotDeployed` is raised
    """
    from sqlalchemy import update

    from intentkit.config.db import get_session
    from intentkit.models.agent.db import AgentTable

    # Given: create agent then archive it directly in DB
    agent_data = AgentCreate(id="auto-agent-archived", name="Archived Agent")
    await create_agent(agent_data)

    async with get_session() as session:
        await session.execute(
            update(AgentTable)
            .where(AgentTable.id == "auto-agent-archived")
            .values(archived_at=datetime.now(timezone.utc))
        )
        await session.commit()

    # When/Then: list
    with pytest.raises(IntentKitAPIError) as exc_info:
        await list_autonomous_tasks("auto-agent-archived")
    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "AgentNotDeployed"

    # When/Then: add
    with pytest.raises(IntentKitAPIError) as exc_info:
        await add_autonomous_task(
            "auto-agent-archived",
            AutonomousCreateRequest(cron="*/5 * * * *", prompt="fail"),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "AgentNotDeployed"


@pytest.mark.bdd
async def test_update_autonomous_task_status():
    """
    Scenario: Update Autonomous Task Status

    Given a deployed agent with an enabled autonomous task
    When I call `update_autonomous_task_status` with `status=running` and a `next_run_time`
    Then the task's status and next_run_time are updated
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-6", name="Status Agent")
    await create_agent(agent_data)

    created = await add_autonomous_task(
        "auto-agent-6",
        AutonomousCreateRequest(
            name="Status Task",
            cron="0 * * * *",
            prompt="Check status",
            enabled=True,
        ),
    )
    assert created.status == AgentAutonomousStatus.WAITING

    # When
    next_run = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    updated = await update_autonomous_task_status(
        "auto-agent-6",
        created.id,
        AgentAutonomousStatus.RUNNING,
        next_run,
    )

    # Then
    assert updated.status == AgentAutonomousStatus.RUNNING
    assert updated.next_run_time == next_run


@pytest.mark.bdd
async def test_disabled_task_has_no_status():
    """
    Scenario: Disabled Task Has No Status

    Given a deployed agent
    When I add an autonomous task with `enabled=False`
    Then the task's `status` is `None`
    And `next_run_time` is `None`
    """
    # Given
    agent_data = AgentCreate(id="auto-agent-7", name="Disabled Agent")
    await create_agent(agent_data)

    # When
    task = await add_autonomous_task(
        "auto-agent-7",
        AutonomousCreateRequest(
            name="Disabled Task",
            cron="*/5 * * * *",
            prompt="This is disabled",
            enabled=False,
        ),
    )

    # Then
    assert task.status is None
    assert task.next_run_time is None
