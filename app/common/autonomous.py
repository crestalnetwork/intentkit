from pydantic import BaseModel, Field

from intentkit.models.agent import AgentAutonomous


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


class AllTasksAgentGroup(BaseModel):
    """Response model for tasks grouped by agent."""

    agent_id: str
    agent_slug: str | None = None
    agent_name: str | None = None
    agent_image: str | None = None
    tasks: list[AutonomousResponse]
