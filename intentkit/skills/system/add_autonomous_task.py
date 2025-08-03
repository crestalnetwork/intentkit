from typing import Optional

from pydantic import BaseModel, Field

from intentkit.models.agent import AgentAutonomous
from intentkit.skills.system.base import SystemBaseTool


class AddAutonomousTaskInput(BaseModel):
    """Input model for add_autonomous_task skill."""

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
    prompt: str = Field(description="Special prompt used during autonomous operation")


class AddAutonomousTaskOutput(BaseModel):
    """Output model for add_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The created autonomous task configuration"
    )


class AddAutonomousTask(SystemBaseTool):
    """Skill to add a new autonomous task to an agent."""

    name: str = "system_add_autonomous_task"
    description: str = (
        "Add a new autonomous task configuration to the agent. "
        "Allows setting up scheduled operations with custom prompts and intervals. "
        "The minutes and cron fields are mutually exclusive. But you must provide one of them. "
        "If user want to add a condition task, you can add a 5 minutes task to check the condition. "
        "If the user does not explicitly state that the condition task should be executed continuously, "
        "then add in the task prompt that it will delete itself after successful execution. "
    )
    args_schema = AddAutonomousTaskInput

    async def _arun(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        minutes: Optional[int] = None,
        cron: Optional[str] = None,
        prompt: str = "",
        **kwargs,
    ) -> AddAutonomousTaskOutput:
        """Add an autonomous task to the agent.

        Args:
            name: Display name of the task
            description: Description of the task
            minutes: Interval in minutes (mutually exclusive with cron)
            cron: Cron expression (mutually exclusive with minutes)
            prompt: Special prompt for autonomous operation
            config: Runtime configuration containing agent context

        Returns:
            AddAutonomousTaskOutput: The created task
        """
        context = self.get_context()
        agent_id = context.agent_id

        task = AgentAutonomous(
            name=name,
            description=description,
            minutes=minutes,
            cron=cron,
            prompt=prompt,
            enabled=True,
        )

        created_task = await self.skill_store.add_autonomous_task(agent_id, task)

        return AddAutonomousTaskOutput(task=created_task)
