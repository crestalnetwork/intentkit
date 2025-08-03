from typing import Optional

from pydantic import BaseModel, Field

from intentkit.models.agent import AgentAutonomous
from intentkit.skills.system.base import SystemBaseTool


class EditAutonomousTaskInput(BaseModel):
    """Input model for edit_autonomous_task skill."""

    task_id: str = Field(
        description="The unique identifier of the autonomous task to edit"
    )
    name: Optional[str] = Field(
        default=None,
        description="Display name of the autonomous task configuration",
        max_length=50,
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the autonomous task configuration",
        max_length=200,
    )
    minutes: Optional[int] = Field(
        default=None,
        description="Interval in minutes between operations, mutually exclusive with cron",
    )
    cron: Optional[str] = Field(
        default=None,
        description="Cron expression for scheduling operations, mutually exclusive with minutes",
    )
    prompt: Optional[str] = Field(
        default=None, description="Special prompt used during autonomous operation"
    )
    enabled: Optional[bool] = Field(
        default=None, description="Whether the autonomous task is enabled"
    )


class EditAutonomousTaskOutput(BaseModel):
    """Output model for edit_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The updated autonomous task configuration"
    )


class EditAutonomousTask(SystemBaseTool):
    """Skill to edit an existing autonomous task for an agent."""

    name: str = "system_edit_autonomous_task"
    description: str = (
        "Edit an existing autonomous task configuration for the agent. "
        "Allows updating the name, description, schedule (minutes or cron), prompt, and enabled status. "
        "Only provided fields will be updated; omitted fields will keep their current values. "
        "The minutes and cron fields are mutually exclusive. Do not provide both of them. "
    )
    args_schema = EditAutonomousTaskInput

    async def _arun(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        minutes: Optional[int] = None,
        cron: Optional[str] = None,
        prompt: Optional[str] = None,
        enabled: Optional[bool] = None,
        **kwargs,
    ) -> EditAutonomousTaskOutput:
        """Edit an autonomous task for the agent.

        Args:
            task_id: ID of the task to edit
            name: Display name of the task
            description: Description of the task
            minutes: Interval in minutes (mutually exclusive with cron)
            cron: Cron expression (mutually exclusive with minutes)
            prompt: Special prompt for autonomous operation
            enabled: Whether the task is enabled
            config: Runtime configuration containing agent context

        Returns:
            EditAutonomousTaskOutput: The updated task
        """
        context = self.get_context()
        agent_id = context.agent_id

        if minutes is not None and cron is not None:
            raise ValueError("minutes and cron are mutually exclusive")

        # Build the updates dictionary with only provided fields
        task_updates = {}
        if name is not None:
            task_updates["name"] = name
        if description is not None:
            task_updates["description"] = description
        if minutes is not None:
            task_updates["minutes"] = minutes
            task_updates["cron"] = None
        if cron is not None:
            task_updates["cron"] = cron
            task_updates["minutes"] = None
        if prompt is not None:
            task_updates["prompt"] = prompt
        if enabled is not None:
            task_updates["enabled"] = enabled

        updated_task = await self.skill_store.update_autonomous_task(
            agent_id, task_id, task_updates
        )

        return EditAutonomousTaskOutput(task=updated_task)
