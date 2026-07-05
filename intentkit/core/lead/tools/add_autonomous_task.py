"""Tool to add an autonomous task to the team."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import add_autonomous_task
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.autonomous import AutonomousCreateRequest, AutonomousTask


class AddAutonomousTaskInput(BaseModel):
    """Input model for add_autonomous_task tool."""

    cron: str = Field(description="Cron expression for scheduling")
    prompt: str = Field(description="Special prompt for autonomous operation")
    name: str | None = Field(default=None, description="Display name of the task")
    description: str | None = Field(default=None, description="Description of the task")
    enabled: bool = Field(default=True, description="Whether the task is enabled")
    target_agent_id: str | None = Field(
        default=None,
        description=(
            "Optional team agent to run the task on directly. Leave empty to let "
            "the team lead read the prompt and decide which agent to delegate to."
        ),
    )


class AddAutonomousTaskOutput(BaseModel):
    """Output model for add_autonomous_task tool."""

    task: AutonomousTask = Field(
        description="The created autonomous task configuration"
    )


class LeadAddAutonomousTask(LeadTool):
    """Tool to add a new autonomous task to the team."""

    name: str = "lead_add_autonomous_task"
    description: str = (
        "Add a new autonomous task to the team. Tasks run on a cron schedule. "
        "Provide a cron expression. Set target_agent_id to pin the task to a "
        "specific agent; otherwise the team lead decides delegation from the "
        "prompt. "
        "If the user wants a condition task, add a 5 minute task (using cron) to "
        "check the condition. If the user does not explicitly state that the "
        "condition task should run continuously, instruct the task to delete "
        "itself after successful execution. "
    )
    args_schema: ArgsSchema | None = AddAutonomousTaskInput

    @override
    async def _arun(
        self,
        cron: str,
        prompt: str,
        name: str | None = None,
        description: str | None = None,
        enabled: bool = True,
        target_agent_id: str | None = None,
        **kwargs: Any,
    ) -> AddAutonomousTaskOutput:
        context = self.get_context()
        assert context.team_id is not None

        task_request = AutonomousCreateRequest(
            name=name,
            description=description,
            cron=cron,
            prompt=prompt,
            enabled=enabled,
            target_agent_id=target_agent_id,
        )
        created_task = await add_autonomous_task(
            context.team_id, task_request, created_by=context.user_id
        )
        return AddAutonomousTaskOutput(task=created_task)


lead_add_autonomous_task_tool = LeadAddAutonomousTask()
