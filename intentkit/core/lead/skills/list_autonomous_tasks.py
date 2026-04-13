"""Skill to list autonomous tasks for a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import list_autonomous_tasks
from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent import AgentAutonomous


class ListAutonomousTasksInput(BaseModel):
    """Input model for list_autonomous_tasks skill."""

    agent_id: str = Field(description="The ID of the agent to list tasks for")


class ListAutonomousTasksOutput(BaseModel):
    """Output model for list_autonomous_tasks skill."""

    tasks: list[AgentAutonomous] = Field(
        description="List of autonomous task configurations for the agent"
    )


class LeadListAutonomousTasks(LeadSkill):
    """Skill to list all autonomous tasks for a team agent."""

    name: str = "lead_list_autonomous_tasks"
    description: str = (
        "List all autonomous task configurations for a team agent. "
        "Returns details about each task including scheduling, prompts, and status."
    )
    args_schema: ArgsSchema | None = ListAutonomousTasksInput

    @override
    async def _arun(self, agent_id: str, **kwargs: Any) -> ListAutonomousTasksOutput:
        context = self.get_context()
        assert context.team_id is not None
        await verify_agent_in_team(agent_id, context.team_id)
        tasks = await list_autonomous_tasks(agent_id)
        return ListAutonomousTasksOutput(tasks=tasks)


lead_list_autonomous_tasks_skill = LeadListAutonomousTasks()
