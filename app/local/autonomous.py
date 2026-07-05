import logging

from fastapi import APIRouter, BackgroundTasks, Body, Path, Query, Response

from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    get_autonomous_execution_messages,
    get_autonomous_task,
    get_fresh_running_execution,
    list_autonomous_executions,
    list_team_autonomous_tasks,
    update_autonomous_task,
)
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousExecutionTrigger,
    AutonomousUpdateRequest,
)
from intentkit.models.chat import ChatMessage
from intentkit.utils.error import IntentKitAPIError

from app.common.autonomous import (
    AutonomousExecutionsResponse,
    AutonomousResponse,
    to_autonomous_response,
    to_autonomous_responses,
)
from app.entrypoints.autonomous import run_autonomous_task
from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID

autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


@autonomous_router.get(
    "/autonomous",
    tags=["Autonomous"],
    operation_id="list_all_autonomous",
    summary="List Autonomous Tasks",
)
async def list_all_autonomous() -> list[AutonomousResponse]:
    """List all autonomous tasks of the team."""
    tasks = await list_team_autonomous_tasks(LEAD_TEAM_ID)
    return await to_autonomous_responses(tasks)


@autonomous_router.get(
    "/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="get_autonomous",
    summary="Get Autonomous Task",
)
async def get_autonomous(
    task_id: str = Path(..., description="ID of the autonomous task"),
) -> AutonomousResponse:
    """Get a single autonomous task."""
    task = await get_autonomous_task(LEAD_TEAM_ID, task_id)
    return await to_autonomous_response(task)


@autonomous_router.post(
    "/autonomous",
    tags=["Autonomous"],
    status_code=201,
    operation_id="add_autonomous",
    summary="Add Autonomous Task",
)
async def add_autonomous(
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
) -> AutonomousResponse:
    """Add a new autonomous task to the team."""
    added_task = await add_autonomous_task(
        LEAD_TEAM_ID, task_request, created_by=LEAD_USER_ID
    )
    return await to_autonomous_response(added_task)


@autonomous_router.patch(
    "/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="update_autonomous",
    summary="Update Autonomous Task",
)
async def update_autonomous(
    task_id: str = Path(..., description="ID of the autonomous task"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
) -> AutonomousResponse:
    """Update a specific autonomous task."""
    updated_task = await update_autonomous_task(LEAD_TEAM_ID, task_id, task_update)
    return await to_autonomous_response(updated_task)


@autonomous_router.delete(
    "/autonomous/{task_id}",
    tags=["Autonomous"],
    status_code=204,
    operation_id="delete_autonomous",
    summary="Delete Autonomous Task",
)
async def delete_autonomous(
    task_id: str = Path(..., description="ID of the autonomous task"),
) -> Response:
    """Delete a specific autonomous task."""
    await delete_autonomous_task(LEAD_TEAM_ID, task_id)
    return Response(status_code=204)


@autonomous_router.post(
    "/autonomous/{task_id}/execute",
    tags=["Autonomous"],
    status_code=202,
    operation_id="execute_autonomous",
    summary="Run Autonomous Task Now",
)
async def execute_autonomous(
    background_tasks: BackgroundTasks,
    task_id: str = Path(..., description="ID of the autonomous task"),
) -> Response:
    """Trigger one manual run of an autonomous task.

    The run starts in the background; poll the executions list to follow it.
    Works for disabled tasks too. Returns 409 when a run of this task is
    already in progress.
    """
    task = await get_autonomous_task(LEAD_TEAM_ID, task_id)
    if await get_fresh_running_execution(task_id):
        raise IntentKitAPIError(
            409,
            "AutonomousTaskRunning",
            "Task is currently running, try again later.",
        )
    background_tasks.add_task(
        run_autonomous_task,
        team_id=LEAD_TEAM_ID,
        owner_user_id=LEAD_USER_ID,
        task_id=task.id,
        prompt=task.prompt,
        target_agent_id=task.target_agent_id,
        trigger=AutonomousExecutionTrigger.MANUAL,
        triggered_by=LEAD_USER_ID,
    )
    return Response(status_code=202)


@autonomous_router.get(
    "/autonomous/{task_id}/executions",
    tags=["Autonomous"],
    operation_id="list_autonomous_executions",
    summary="List Autonomous Task Executions",
)
async def list_executions(
    task_id: str = Path(..., description="ID of the autonomous task"),
    cursor: str | None = Query(None, description="Cursor for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
) -> AutonomousExecutionsResponse:
    """List executions of an autonomous task, newest first."""
    executions, has_more, next_cursor = await list_autonomous_executions(
        LEAD_TEAM_ID, task_id, cursor=cursor, limit=limit
    )
    return AutonomousExecutionsResponse(
        data=executions, has_more=has_more, next_cursor=next_cursor
    )


@autonomous_router.get(
    "/autonomous/{task_id}/executions/{execution_id}/messages",
    tags=["Autonomous"],
    operation_id="get_autonomous_execution_messages",
    summary="Get Autonomous Execution Log",
)
async def get_execution_messages(
    task_id: str = Path(..., description="ID of the autonomous task"),
    execution_id: str = Path(..., description="Execution ID"),
) -> list[ChatMessage]:
    """Get the chat message log of one execution, oldest first."""
    return await get_autonomous_execution_messages(LEAD_TEAM_ID, task_id, execution_id)
