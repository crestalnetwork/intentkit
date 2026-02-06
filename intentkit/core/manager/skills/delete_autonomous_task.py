from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import delete_autonomous_task
from intentkit.core.manager.skills.base import ManagerSkill


class DeleteAutonomousTaskInput(BaseModel):
    """Input model for delete_autonomous_task skill."""

    task_id: str = Field(
        description="The unique identifier of the autonomous task to delete"
    )


class DeleteAutonomousTaskOutput(BaseModel):
    """Output model for delete_autonomous_task skill."""

    success: bool = Field(
        description="Whether the task was successfully deleted", default=True
    )
    message: str = Field(description="Confirmation message about the deletion")


class DeleteAutonomousTask(ManagerSkill):
    """Skill to delete an autonomous task from an agent."""

    name: str = "system_delete_autonomous_task"
    description: str = (
        "Delete an autonomous task configuration from the agent. "
        "Requires the task ID to identify which task to remove."
    )
    args_schema: ArgsSchema | None = DeleteAutonomousTaskInput

    @override
    async def _arun(
        self,
        task_id: str,
        **kwargs: Any,
    ) -> DeleteAutonomousTaskOutput:
        """Delete an autonomous task from the agent.

        Args:
            task_id: The ID of the task to delete
            config: Runtime configuration containing agent context

        Returns:
            DeleteAutonomousTaskOutput: Confirmation of deletion
        """
        context = self.get_context()
        agent = context.agent

        await delete_autonomous_task(agent.id, task_id)

        return DeleteAutonomousTaskOutput(
            success=True, message=f"Successfully deleted autonomous task {task_id}"
        )


# Shared skill instances
delete_autonomous_task_skill = DeleteAutonomousTask()
