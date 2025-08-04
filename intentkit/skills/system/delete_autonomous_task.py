from pydantic import BaseModel, Field

from intentkit.skills.system.base import SystemBaseTool


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


class DeleteAutonomousTask(SystemBaseTool):
    """Skill to delete an autonomous task from an agent."""

    name: str = "system_delete_autonomous_task"
    description: str = (
        "Delete an autonomous task configuration from the agent. "
        "Requires the task ID to identify which task to remove."
    )
    args_schema = DeleteAutonomousTaskInput

    async def _arun(
        self,
        task_id: str,
        **kwargs,
    ) -> DeleteAutonomousTaskOutput:
        """Delete an autonomous task from the agent.

        Args:
            task_id: The ID of the task to delete
            config: Runtime configuration containing agent context

        Returns:
            DeleteAutonomousTaskOutput: Confirmation of deletion
        """
        context = self.get_context()
        agent_id = context.agent_id

        await self.skill_store.delete_autonomous_task(agent_id, task_id)

        return DeleteAutonomousTaskOutput(
            success=True, message=f"Successfully deleted autonomous task {task_id}"
        )
