import logging

from fastapi import APIRouter, Body, Path, Response
from pydantic import Field

from intentkit.core.agent import get_agent
from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    update_autonomous_task,
)
from intentkit.models.agent import AgentAutonomous
from intentkit.models.agent.autonomous import (
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
)
from intentkit.utils.error import IntentKitAPIError

autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


class AutonomousResponse(AgentAutonomous):
    """Response model for autonomous task with additional computed fields."""

    chat_id: str = Field(
        description="The chat ID associated with this autonomous task",
    )

    @classmethod
    def from_model(cls, model: AgentAutonomous) -> "AutonomousResponse":
        """Convert from AgentAutonomous model to AutonomousResponse."""
        data = model.model_dump()
        data["chat_id"] = f"autonomous-{model.id}"
        return cls.model_validate(data)


@autonomous_router.get(
    "/agents/{agent_id}/autonomous",
    tags=["Autonomous"],
    operation_id="list_autonomous",
    summary="List Autonomous Tasks",
)
async def list_autonomous(
    agent_id: str = Path(..., description="ID of the agent"),
) -> list[AutonomousResponse]:
    """List all autonomous tasks for an agent.

    **Path Parameters:**
    * `agent_id` - ID of the agent

    **Returns:**
    * `list[AutonomousResponse]` - List of autonomous tasks
    """
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    tasks = agent.autonomous or []
    return [AutonomousResponse.from_model(task) for task in tasks]


@autonomous_router.post(
    "/agents/{agent_id}/autonomous",
    tags=["Autonomous"],
    status_code=201,
    operation_id="add_autonomous",
    summary="Add Autonomous Task",
)
async def add_autonomous(
    agent_id: str = Path(..., description="ID of the agent"),
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
) -> AutonomousResponse:
    """Add a new autonomous task to an agent.

    **Path Parameters:**
    * `agent_id` - ID of the agent

    **Request Body:**
    * `task_request` - Task configuration

    **Returns:**
    * `AutonomousResponse` - Created autonomous task
    """
    # core function handles validation and DB update
    added_task = await add_autonomous_task(agent_id, task_request)
    return AutonomousResponse.from_model(added_task)


@autonomous_router.patch(
    "/agents/{agent_id}/autonomous/{autonomous_id}",
    tags=["Autonomous"],
    operation_id="update_autonomous",
    summary="Update Autonomous Task",
)
async def update_autonomous(
    agent_id: str = Path(..., description="ID of the agent"),
    autonomous_id: str = Path(..., description="ID of the autonomous task"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
) -> AutonomousResponse:
    """Update a specific autonomous task.

    **Path Parameters:**
    * `agent_id` - ID of the agent
    * `autonomous_id` - ID of the autonomous task to update

    **Request Body:**
    * `task_update` - Fields to update

    **Returns:**
    * `AutonomousResponse` - Updated autonomous task
    """
    # core function handles validation and DB update
    updated_task = await update_autonomous_task(agent_id, autonomous_id, task_update)
    return AutonomousResponse.from_model(updated_task)


@autonomous_router.delete(
    "/agents/{agent_id}/autonomous/{autonomous_id}",
    tags=["Autonomous"],
    status_code=204,
    operation_id="delete_autonomous",
    summary="Delete Autonomous Task",
)
async def delete_autonomous(
    agent_id: str = Path(..., description="ID of the agent"),
    autonomous_id: str = Path(..., description="ID of the autonomous task"),
) -> Response:
    """Delete a specific autonomous task.

    **Path Parameters:**
    * `agent_id` - ID of the agent
    * `autonomous_id` - ID of the autonomous task to delete
    """
    # core function handles validation and DB update
    await delete_autonomous_task(agent_id, autonomous_id)
    return Response(status_code=204)
