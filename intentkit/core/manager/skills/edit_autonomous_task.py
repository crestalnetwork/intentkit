from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import update_autonomous_task
from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.models.agent import AgentAutonomous
from intentkit.models.agent.autonomous import AutonomousUpdateRequest


class EditAutonomousTaskInput(AutonomousUpdateRequest):
    """Input model for edit_autonomous_task skill."""

    task_id: str = Field(
        description="The unique identifier of the autonomous task to edit"
    )


class EditAutonomousTaskOutput(BaseModel):
    """Output model for edit_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The updated autonomous task configuration"
    )


class EditAutonomousTask(ManagerSkill):
    """Skill to edit an existing autonomous task for an agent."""

    name: str = "system_edit_autonomous_task"
    description: str = (
        "Edit an existing autonomous task configuration for the agent. "
        "Allows updating the name, description, schedule (cron), prompt, and enabled status. "
        "Only provided fields will be updated; omitted fields will keep their current values. "
    )
    args_schema: ArgsSchema | None = EditAutonomousTaskInput

    async def _arun(
        self,
        task_id: str,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        prompt: str | None = None,
        enabled: bool | None = None,
        has_memory: bool | None = None,
        **kwargs: Any,
    ) -> EditAutonomousTaskOutput:
        """Edit an autonomous task for the agent.

        Args:
            task_id: ID of the task to edit
            name: Display name of the task
            description: Description of the task
            cron: Cron expression
            prompt: Special prompt for autonomous operation
            enabled: Whether the task is enabled
            has_memory: Whether to retain memory between runs
            config: Runtime configuration containing agent context

        Returns:
            EditAutonomousTaskOutput: The updated task
        """
        context = self.get_context()
        agent = context.agent

        task_update = AutonomousUpdateRequest(
            name=name,
            description=description,
            cron=cron,
            prompt=prompt,
            enabled=enabled,
            has_memory=has_memory,
        )

        updated_task = await update_autonomous_task(agent.id, task_id, task_update)

        return EditAutonomousTaskOutput(task=updated_task)


# Shared skill instances
edit_autonomous_task_skill = EditAutonomousTask()
