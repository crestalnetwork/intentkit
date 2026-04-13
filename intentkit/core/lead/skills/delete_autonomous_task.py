"""Skill to delete an autonomous task from a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import delete_autonomous_task
from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill


class DeleteAutonomousTaskInput(BaseModel):
    """Input model for delete_autonomous_task skill."""

    agent_id: str = Field(description="The ID of the agent owning the task")
    task_id: str = Field(
        description="The unique identifier of the autonomous task to delete"
    )


class DeleteAutonomousTaskOutput(BaseModel):
    """Output model for delete_autonomous_task skill."""

    success: bool = Field(
        description="Whether the task was successfully deleted", default=True
    )
    message: str = Field(description="Confirmation message about the deletion")


class LeadDeleteAutonomousTask(LeadSkill):
    """Skill to delete an autonomous task from a team agent."""

    name: str = "lead_delete_autonomous_task"
    description: str = (
        "Delete an autonomous task configuration from a team agent. "
        "Requires the agent_id and task_id to identify which task to remove."
    )
    args_schema: ArgsSchema | None = DeleteAutonomousTaskInput

    @override
    async def _arun(
        self,
        agent_id: str,
        task_id: str,
        **kwargs: Any,
    ) -> DeleteAutonomousTaskOutput:
        context = self.get_context()
        assert context.team_id is not None
        await verify_agent_in_team(agent_id, context.team_id)
        await delete_autonomous_task(agent_id, task_id)
        return DeleteAutonomousTaskOutput(
            success=True, message=f"Successfully deleted autonomous task {task_id}"
        )


lead_delete_autonomous_task_skill = LeadDeleteAutonomousTask()
