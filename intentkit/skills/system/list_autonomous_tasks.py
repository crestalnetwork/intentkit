from typing import List

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from intentkit.models.agent import AgentAutonomous
from intentkit.skills.system.base import SystemBaseTool


class ListAutonomousTasksInput(BaseModel):
    """Input model for list_autonomous_tasks skill."""

    pass


class ListAutonomousTasksOutput(BaseModel):
    """Output model for list_autonomous_tasks skill."""

    tasks: List[AgentAutonomous] = Field(
        description="List of autonomous task configurations for the agent"
    )


class ListAutonomousTasks(SystemBaseTool):
    """Skill to list all autonomous tasks for an agent."""

    name: str = "system_list_autonomous_tasks"
    description: str = (
        "List all autonomous task configurations for the agent. "
        "Returns details about each task including scheduling, prompts, and status."
    )
    args_schema = ListAutonomousTasksInput

    async def _arun(
        self,
        config: RunnableConfig,
        **kwargs,
    ) -> ListAutonomousTasksOutput:
        """List autonomous tasks for the agent.

        Args:
            config: Runtime configuration containing agent context

        Returns:
            ListAutonomousTasksOutput: List of autonomous tasks
        """
        context = self.context_from_config(config)
        agent_id = context.agent_id

        tasks = await self.skill_store.list_autonomous_tasks(agent_id)

        return ListAutonomousTasksOutput(tasks=tasks)
