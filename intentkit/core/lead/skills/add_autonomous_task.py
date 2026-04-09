"""Skill to add an autonomous task to a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import add_autonomous_task
from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent import AgentAutonomous
from intentkit.models.agent.autonomous import AutonomousCreateRequest


class AddAutonomousTaskInput(BaseModel):
    """Input model for add_autonomous_task skill."""

    agent_id: str = Field(description="The ID of the agent to add the task to")
    cron: str = Field(description="Cron expression for scheduling")
    prompt: str = Field(description="Special prompt for autonomous operation")
    name: str | None = Field(default=None, description="Display name of the task")
    description: str | None = Field(default=None, description="Description of the task")
    enabled: bool = Field(default=True, description="Whether the task is enabled")
    has_memory: bool = Field(
        default=False, description="Whether to retain memory between runs"
    )


class AddAutonomousTaskOutput(BaseModel):
    """Output model for add_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The created autonomous task configuration"
    )


class LeadAddAutonomousTask(LeadSkill):
    """Skill to add a new autonomous task to a team agent."""

    name: str = "lead_add_autonomous_task"
    description: str = (
        "Add a new autonomous task configuration to a team agent. "
        "Allows setting up scheduled operations with custom prompts and intervals. "
        "User must provide a cron expression for scheduling. "
        "If user want to add a condition task, you can add a 5 minutes task (using cron) to check the condition. "
        "If the user does not explicitly state that the condition task should be executed continuously, "
        "then add in the task prompt that it will delete itself after successful execution. "
    )
    args_schema: ArgsSchema | None = AddAutonomousTaskInput

    @override
    async def _arun(
        self,
        agent_id: str,
        cron: str,
        prompt: str,
        name: str | None = None,
        description: str | None = None,
        enabled: bool = True,
        has_memory: bool = False,
        **kwargs: Any,
    ) -> AddAutonomousTaskOutput:
        context = self.get_context()
        await verify_agent_in_team(agent_id, context.team_id)

        task_request = AutonomousCreateRequest(
            name=name,
            description=description,
            cron=cron,
            prompt=prompt,
            enabled=enabled,
            has_memory=has_memory,
        )
        created_task = await add_autonomous_task(agent_id, task_request)
        return AddAutonomousTaskOutput(task=created_task)


lead_add_autonomous_task_skill = LeadAddAutonomousTask()
