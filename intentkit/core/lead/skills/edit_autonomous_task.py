"""Skill to edit an autonomous task on a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import update_autonomous_task
from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent import AgentAutonomous
from intentkit.models.agent.autonomous import AutonomousUpdateRequest


class EditAutonomousTaskInput(BaseModel):
    """Input model for edit_autonomous_task skill."""

    agent_id: str = Field(description="The ID of the agent owning the task")
    task_id: str = Field(
        description="The unique identifier of the autonomous task to edit"
    )
    name: str | None = Field(default=None, description="Display name of the task")
    description: str | None = Field(default=None, description="Description of the task")
    cron: str | None = Field(default=None, description="Cron expression")
    prompt: str | None = Field(default=None, description="Special prompt")
    enabled: bool | None = Field(default=None, description="Whether enabled")
    has_memory: bool | None = Field(
        default=None, description="Whether to retain memory between runs"
    )


class EditAutonomousTaskOutput(BaseModel):
    """Output model for edit_autonomous_task skill."""

    task: AgentAutonomous = Field(
        description="The updated autonomous task configuration"
    )


class LeadEditAutonomousTask(LeadSkill):
    """Skill to edit an existing autonomous task for a team agent."""

    name: str = "lead_edit_autonomous_task"
    description: str = (
        "Edit an existing autonomous task configuration for a team agent. "
        "Only provided fields will be updated; omitted fields will keep their current values."
    )
    args_schema: ArgsSchema | None = EditAutonomousTaskInput

    @override
    async def _arun(
        self,
        agent_id: str,
        task_id: str,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        prompt: str | None = None,
        enabled: bool | None = None,
        has_memory: bool | None = None,
        **kwargs: Any,
    ) -> EditAutonomousTaskOutput:
        context = self.get_context()
        await verify_agent_in_team(agent_id, context.team_id)

        task_update = AutonomousUpdateRequest(
            name=name,
            description=description,
            cron=cron,
            prompt=prompt,
            enabled=enabled,
            has_memory=has_memory,
        )
        updated_task = await update_autonomous_task(agent_id, task_id, task_update)
        return EditAutonomousTaskOutput(task=updated_task)


lead_edit_autonomous_task_skill = LeadEditAutonomousTask()
