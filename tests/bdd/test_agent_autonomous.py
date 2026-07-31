"""
BDD Tests: Team Autonomous Task Management

Feature: Autonomous Task Lifecycle
As an IntentKit operator, I want to manage autonomous tasks on a team
so that the team can execute scheduled actions independently.
"""

from datetime import UTC, datetime

import pytest

from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    list_team_autonomous_tasks,
    update_autonomous_task,
    update_autonomous_task_status,
)
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousTaskStatus,
    AutonomousUpdateRequest,
)
from intentkit.utils.error import IntentKitAPIError

# Use session-scoped event loop to share DB connections across tests
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_add_autonomous_task_to_team():
    """
    Scenario: Add an Autonomous Task to a Team

    Given a team `id=auto-team-1`
    When I call `add_autonomous_task` with a cron schedule and prompt
    Then a task is persisted with correct fields owned by the team
    """
    task_request = AutonomousCreateRequest(
        name="Daily Report",
        description="Generate a daily report",
        cron="0 9 * * *",
        prompt="Generate the daily report",
        enabled=True,
    )
    task = await add_autonomous_task("auto-team-1", task_request)

    assert task.id
    assert task.team_id == "auto-team-1"
    assert task.cron == "0 9 * * *"
    assert task.prompt == "Generate the daily report"
    assert task.status == AutonomousTaskStatus.WAITING


@pytest.mark.bdd
async def test_list_autonomous_tasks():
    """
    Scenario: List a Team's Autonomous Tasks
    """
    task1 = AutonomousCreateRequest(cron="0 9 * * *", prompt="One")
    task2 = AutonomousCreateRequest(cron="0 10 * * *", prompt="Two")
    await add_autonomous_task("auto-team-2", task1)
    await add_autonomous_task("auto-team-2", task2)

    tasks = await list_team_autonomous_tasks("auto-team-2")
    assert len(tasks) == 2


@pytest.mark.bdd
async def test_update_autonomous_task_partial():
    """
    Scenario: Partially Update an Autonomous Task

    When I call `update_autonomous_task` with only `name` updated
    Then only that field changes and the rest are preserved
    """
    created = await add_autonomous_task(
        "auto-team-3",
        AutonomousCreateRequest(name="Old", cron="0 9 * * *", prompt="keep me"),
    )

    update = AutonomousUpdateRequest(name="New")
    updated = await update_autonomous_task("auto-team-3", created.id, update)

    assert updated.name == "New"
    assert updated.prompt == "keep me"
    assert updated.cron == "0 9 * * *"


@pytest.mark.bdd
async def test_delete_autonomous_task():
    """
    Scenario: Delete an Autonomous Task
    """
    created = await add_autonomous_task(
        "auto-team-4",
        AutonomousCreateRequest(cron="0 9 * * *", prompt="bye"),
    )

    await delete_autonomous_task("auto-team-4", created.id)

    tasks = await list_team_autonomous_tasks("auto-team-4")
    assert all(t.id != created.id for t in tasks)


@pytest.mark.bdd
async def test_add_task_with_invalid_target_agent_fails():
    """
    Scenario: Adding a Task Targeting an Unknown Agent Fails
    """
    task_request = AutonomousCreateRequest(
        cron="0 9 * * *",
        prompt="x",
        target_agent_id="no-such-agent",
    )
    with pytest.raises(IntentKitAPIError):
        await add_autonomous_task("auto-team-5", task_request)


@pytest.mark.bdd
async def test_delete_nonexistent_task_fails():
    """
    Scenario: Deleting a Nonexistent Task Fails
    """
    with pytest.raises(IntentKitAPIError):
        await delete_autonomous_task("auto-team-6", "no-such-task")


@pytest.mark.bdd
async def test_update_autonomous_task_status():
    """
    Scenario: Update a Task's Runtime Status

    When I call `update_autonomous_task_status` with `status=running` and a `next_run_time`
    Then the task reflects the new runtime state
    """
    created = await add_autonomous_task(
        "auto-team-7",
        AutonomousCreateRequest(cron="0 9 * * *", prompt="x"),
    )

    next_run = datetime(2030, 1, 1, tzinfo=UTC)
    updated = await update_autonomous_task_status(
        "auto-team-7", created.id, AutonomousTaskStatus.RUNNING, next_run
    )

    assert updated.status == AutonomousTaskStatus.RUNNING
    assert updated.next_run_time == next_run


@pytest.mark.bdd
async def test_disabled_task_has_no_status():
    """
    Scenario: A Disabled Task Has No Runtime Status
    """
    task = await add_autonomous_task(
        "auto-team-8",
        AutonomousCreateRequest(cron="0 9 * * *", prompt="x", enabled=False),
    )

    assert task.enabled is False
    assert task.status is None
