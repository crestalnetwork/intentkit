"""Team API autonomous task endpoints."""

import logging

from fastapi import APIRouter, Body, Depends, Path, Response

from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    update_autonomous_task,
)
from intentkit.models.agent.autonomous import (
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
)

from app.local.autonomous import AutonomousResponse
from app.team.agent import get_team_agent
from app.team.auth import verify_team_member

team_autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


@team_autonomous_router.get(
    "/teams/{team_id}/agents/{agent_id}/autonomous",
    tags=["Team Autonomous"],
    operation_id="team_list_autonomous",
    summary="List Autonomous Tasks (Team)",
)
async def list_autonomous(
    agent_id: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AutonomousResponse]:
    """List all autonomous tasks for a team agent."""
    _user_id, team_id = auth
    agent = await get_team_agent(agent_id, team_id)
    tasks = agent.autonomous or []
    return [AutonomousResponse.from_model(task) for task in tasks]


@team_autonomous_router.post(
    "/teams/{team_id}/agents/{agent_id}/autonomous",
    tags=["Team Autonomous"],
    status_code=201,
    operation_id="team_add_autonomous",
    summary="Add Autonomous Task (Team)",
)
async def add_autonomous(
    agent_id: str = Path(..., description="Agent ID"),
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Add a new autonomous task to a team agent."""
    _user_id, team_id = auth
    await get_team_agent(agent_id, team_id)
    added_task = await add_autonomous_task(agent_id, task_request)
    return AutonomousResponse.from_model(added_task)


@team_autonomous_router.patch(
    "/teams/{team_id}/agents/{agent_id}/autonomous/{autonomous_id}",
    tags=["Team Autonomous"],
    operation_id="team_update_autonomous",
    summary="Update Autonomous Task (Team)",
)
async def update_autonomous(
    agent_id: str = Path(..., description="Agent ID"),
    autonomous_id: str = Path(..., description="Autonomous task ID"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Update a specific autonomous task for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(agent_id, team_id)
    updated_task = await update_autonomous_task(agent_id, autonomous_id, task_update)
    return AutonomousResponse.from_model(updated_task)


@team_autonomous_router.delete(
    "/teams/{team_id}/agents/{agent_id}/autonomous/{autonomous_id}",
    tags=["Team Autonomous"],
    status_code=204,
    operation_id="team_delete_autonomous",
    summary="Delete Autonomous Task (Team)",
)
async def delete_autonomous(
    agent_id: str = Path(..., description="Agent ID"),
    autonomous_id: str = Path(..., description="Autonomous task ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Delete a specific autonomous task for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(agent_id, team_id)
    await delete_autonomous_task(agent_id, autonomous_id)
    return Response(status_code=204)
