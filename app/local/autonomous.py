import logging

from epyxid import XID
from fastapi import APIRouter, Body, Path, Response
from pydantic import BaseModel, Field

from intentkit.core.agent import get_agent, patch_agent
from intentkit.models.agent import AgentAutonomous, AgentUpdate
from intentkit.utils.error import IntentKitAPIError

autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


class AutonomousCreateRequest(BaseModel):
    """Request model for creating a new autonomous task."""

    name: str | None = Field(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = Field(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str = Field(
        ...,
        description="Cron expression for scheduling operations",
    )
    prompt: str = Field(
        ...,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool = Field(
        default=False,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool = Field(
        default=True,
        description="Whether to retain conversation memory between autonomous runs.",
    )


class AutonomousUpdateRequest(BaseModel):
    """Request model for modifying an autonomous task."""

    name: str | None = Field(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = Field(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str | None = Field(
        default=None,
        description="Cron expression for scheduling operations",
    )
    prompt: str | None = Field(
        default=None,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool | None = Field(
        default=None,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool | None = Field(
        default=None,
        description="Whether to retain conversation memory between autonomous runs.",
    )


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
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    # Create new task model
    new_task = AgentAutonomous(
        id=str(XID()),
        cron=task_request.cron,
        prompt=task_request.prompt,
        name=task_request.name,
        description=task_request.description,
        enabled=task_request.enabled,
        has_memory=task_request.has_memory,
        status=None,  # Will be normalized
        minutes=None,
        next_run_time=None,
    )
    new_task = new_task.normalize_status_defaults()

    # Determine current tasks
    current_tasks = agent.autonomous or []
    current_tasks.append(new_task)

    # Use model_construct to bypass required field checks for other fields in AgentUpdate
    # and to ensure fields_set only contains 'autonomous' for patch_agent
    update_data = AgentUpdate.model_construct(autonomous=current_tasks)

    updated_agent, _ = await patch_agent(agent_id, update_data, agent.owner)

    # Retrieve the added task from the updated agent to return it
    added_task = next(
        (t for t in (updated_agent.autonomous or []) if t.id == new_task.id), None
    )

    if not added_task:
        raise IntentKitAPIError(
            500, "InternalServerError", "Failed to add autonomous task"
        )

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
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    current_tasks = agent.autonomous or []

    # Find the index of the task to update
    task_index = -1
    for i, task in enumerate(current_tasks):
        if task.id == autonomous_id:
            task_index = i
            break

    if task_index == -1:
        raise IntentKitAPIError(404, "NotFound", "Autonomous task not found")

    # Update the task
    task_to_update = current_tasks[task_index]
    update_dict = task_update.model_dump(exclude_unset=True)

    updated_task = task_to_update.model_copy(update=update_dict)
    updated_task = updated_task.normalize_status_defaults()

    current_tasks[task_index] = updated_task

    # Save changes
    update_data = AgentUpdate.model_construct(autonomous=current_tasks)
    updated_agent, _ = await patch_agent(agent_id, update_data, agent.owner)

    # Retrieve updated task
    result_task = next(
        (t for t in (updated_agent.autonomous or []) if t.id == autonomous_id), None
    )

    if not result_task:
        raise IntentKitAPIError(
            500, "InternalServerError", "Failed to update autonomous task"
        )

    return AutonomousResponse.from_model(result_task)


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
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    current_tasks = agent.autonomous or []

    # Filter out the task to delete
    new_tasks = [task for task in current_tasks if task.id != autonomous_id]

    if len(new_tasks) == len(current_tasks):
        raise IntentKitAPIError(404, "NotFound", "Autonomous task not found")

    # Save changes
    update_data = AgentUpdate.model_construct(autonomous=new_tasks)
    _ = await patch_agent(agent_id, update_data, agent.owner)

    return Response(status_code=204)
