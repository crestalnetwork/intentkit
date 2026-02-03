from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import add_autonomous_task
from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.models.agent import AgentAutonomous
from intentkit.models.agent.autonomous import AutonomousCreateRequest


class AddAutonomousTaskInput(AutonomousCreateRequest):
    """Input model for add_autonomous_task skill."""

    pass


class AddAutonomousTaskOutput(BaseModel):
    """Output model for add_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The created autonomous task configuration"
    )


class AddAutonomousTask(ManagerSkill):
    """Skill to add a new autonomous task to an agent."""

    name: str = "system_add_autonomous_task"
    description: str = (
        "Add a new autonomous task configuration to the agent. "
        "Allows setting up scheduled operations with custom prompts and intervals. "
        "User must provide a cron expression for scheduling. "
        "If user want to add a condition task, you can add a 5 minutes task (using cron) to check the condition. "
        "If the user does not explicitly state that the condition task should be executed continuously, "
        "then add in the task prompt that it will delete itself after successful execution. "
    )
    args_schema: ArgsSchema | None = AddAutonomousTaskInput

    async def _arun(
        self,
        cron: str,
        prompt: str,
        name: str | None = None,
        description: str | None = None,
        enabled: bool = False,
        has_memory: bool = True,
        **kwargs: Any,
    ) -> AddAutonomousTaskOutput:
        """Add an autonomous task to the agent.

        Args:
            cron: Cron expression
            prompt: Special prompt for autonomous operation
            name: Display name of the task
            description: Description of the task
            enabled: Whether the task is enabled
            has_memory: Whether to retain memory between runs
            config: Runtime configuration containing agent context

        Returns:
            AddAutonomousTaskOutput: The created task
        """
        context = self.get_context()
        agent = context.agent

        task_request = AutonomousCreateRequest(
            name=name,
            description=description,
            cron=cron,
            prompt=prompt,
            enabled=enabled,
            has_memory=has_memory,
        )

        created_task = await add_autonomous_task(agent.id, task_request)

        return AddAutonomousTaskOutput(task=created_task)


# Shared skill instances
add_autonomous_task_skill = AddAutonomousTask()
