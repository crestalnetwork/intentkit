"""Team API autonomous task endpoints."""

import logging

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, Query, Response

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
from app.team.auth import verify_team_member

team_autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


@team_autonomous_router.get(
    "/teams/{team_id}/autonomous",
    tags=["Autonomous"],
    operation_id="team_list_autonomous",
    summary="List Autonomous Tasks (Team)",
)
async def list_autonomous(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AutonomousResponse]:
    """List all autonomous tasks of a team."""
    _user_id, team_id = auth
    tasks = await list_team_autonomous_tasks(team_id)
    return await to_autonomous_responses(tasks)


@team_autonomous_router.get(
    "/teams/{team_id}/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="team_get_autonomous",
    summary="Get Autonomous Task (Team)",
)
async def get_autonomous(
    task_id: str = Path(..., description="Autonomous task ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Get a single autonomous task of a team."""
    _user_id, team_id = auth
    task = await get_autonomous_task(team_id, task_id)
    return await to_autonomous_response(task)


@team_autonomous_router.post(
    "/teams/{team_id}/autonomous",
    tags=["Autonomous"],
    status_code=201,
    operation_id="team_add_autonomous",
    summary="Add Autonomous Task (Team)",
)
async def add_autonomous(
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Add a new autonomous task to a team."""
    user_id, team_id = auth
    added_task = await add_autonomous_task(team_id, task_request, created_by=user_id)
    return await to_autonomous_response(added_task)


@team_autonomous_router.patch(
    "/teams/{team_id}/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="team_update_autonomous",
    summary="Update Autonomous Task (Team)",
)
async def update_autonomous(
    task_id: str = Path(..., description="Autonomous task ID"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Update a specific autonomous task of a team."""
    _user_id, team_id = auth
    updated_task = await update_autonomous_task(team_id, task_id, task_update)
    return await to_autonomous_response(updated_task)


@team_autonomous_router.delete(
    "/teams/{team_id}/autonomous/{task_id}",
    tags=["Autonomous"],
    status_code=204,
    operation_id="team_delete_autonomous",
    summary="Delete Autonomous Task (Team)",
)
async def delete_autonomous(
    task_id: str = Path(..., description="Autonomous task ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Delete a specific autonomous task of a team."""
    _user_id, team_id = auth
    await delete_autonomous_task(team_id, task_id)
    return Response(status_code=204)


@team_autonomous_router.post(
    "/teams/{team_id}/autonomous/{task_id}/execute",
    tags=["Autonomous"],
    status_code=202,
    operation_id="team_execute_autonomous",
    summary="Run Autonomous Task Now (Team)",
)
async def execute_autonomous(
    background_tasks: BackgroundTasks,
    task_id: str = Path(..., description="Autonomous task ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Trigger one manual run of an autonomous task.

    The run starts in the background; poll the executions list to follow it.
    Works for disabled tasks too (useful for trying a task out). Returns 409
    when a run of this task is already in progress.
    """
    user_id, team_id = auth
    task = await get_autonomous_task(team_id, task_id)
    if await get_fresh_running_execution(task_id):
        raise IntentKitAPIError(
            409,
            "AutonomousTaskRunning",
            "Task is currently running, try again later.",
        )
    background_tasks.add_task(
        run_autonomous_task,
        team_id=team_id,
        owner_user_id=user_id,
        task_id=task.id,
        prompt=task.prompt,
        target_agent_id=task.target_agent_id,
        trigger=AutonomousExecutionTrigger.MANUAL,
        triggered_by=user_id,
    )
    return Response(status_code=202)


@team_autonomous_router.get(
    "/teams/{team_id}/autonomous/{task_id}/executions",
    tags=["Autonomous"],
    operation_id="team_list_autonomous_executions",
    summary="List Autonomous Task Executions (Team)",
)
async def list_executions(
    task_id: str = Path(..., description="Autonomous task ID"),
    cursor: str | None = Query(None, description="Cursor for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousExecutionsResponse:
    """List executions of an autonomous task, newest first."""
    _user_id, team_id = auth
    executions, has_more, next_cursor = await list_autonomous_executions(
        team_id, task_id, cursor=cursor, limit=limit
    )
    return AutonomousExecutionsResponse(
        data=executions, has_more=has_more, next_cursor=next_cursor
    )


@team_autonomous_router.get(
    "/teams/{team_id}/autonomous/{task_id}/executions/{execution_id}/messages",
    tags=["Autonomous"],
    operation_id="team_get_autonomous_execution_messages",
    summary="Get Autonomous Execution Log (Team)",
)
async def get_execution_messages(
    task_id: str = Path(..., description="Autonomous task ID"),
    execution_id: str = Path(..., description="Execution ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[ChatMessage]:
    """Get the chat message log of one execution, oldest first."""
    _user_id, team_id = auth
    return await get_autonomous_execution_messages(team_id, task_id, execution_id)
