from pydantic import BaseModel, Field

from intentkit.core.agent import AgentInfo, get_agent_infos
from intentkit.models.autonomous import AutonomousExecution, AutonomousTask
from intentkit.models.chat import AUTONOMOUS_CHAT_PREFIX


class AutonomousResponse(AutonomousTask):
    """Response model for an autonomous task with additional computed fields."""

    chat_id: str = Field(
        description="The chat ID associated with this autonomous task",
    )
    target_agent: AgentInfo | None = Field(
        default=None,
        description="Display info of the target agent, resolved at read time",
    )

    @classmethod
    def from_model(cls, model: AutonomousTask) -> "AutonomousResponse":
        """Convert from AutonomousTask model to AutonomousResponse."""
        data = model.model_dump()
        data["chat_id"] = f"{AUTONOMOUS_CHAT_PREFIX}{model.id}"
        return cls.model_validate(data)


async def to_autonomous_responses(
    tasks: list[AutonomousTask],
) -> list[AutonomousResponse]:
    """Convert tasks to responses, attaching target agent display info."""
    responses = [AutonomousResponse.from_model(task) for task in tasks]
    infos = await get_agent_infos(
        r.target_agent_id for r in responses if r.target_agent_id
    )
    for response in responses:
        if response.target_agent_id:
            response.target_agent = infos.get(response.target_agent_id)
    return responses


async def to_autonomous_response(task: AutonomousTask) -> AutonomousResponse:
    """Convert one task to a response with target agent display info."""
    responses = await to_autonomous_responses([task])
    return responses[0]


class AutonomousExecutionsResponse(BaseModel):
    """Cursor-paginated list of autonomous task executions."""

    data: list[AutonomousExecution] = Field(
        description="Executions, newest first",
    )
    has_more: bool = Field(
        description="Whether more executions exist beyond this page",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for the next page (an execution id)",
    )
