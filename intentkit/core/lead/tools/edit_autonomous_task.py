"""Tool to edit a team autonomous task."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import update_autonomous_task
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.autonomous import AutonomousTask, AutonomousUpdateRequest


class EditAutonomousTaskInput(BaseModel):
    """Input model for edit_autonomous_task tool."""

    task_id: str = Field(
        description="The unique identifier of the autonomous task to edit"
    )
    name: str | None = Field(default=None, description="Display name of the task")
    description: str | None = Field(default=None, description="Description of the task")
    cron: str | None = Field(default=None, description="Cron expression")
    prompt: str | None = Field(default=None, description="Special prompt")
    enabled: bool | None = Field(default=None, description="Whether enabled")
    target_agent_id: str | None = Field(
        default=None,
        description="Pin the task to run directly on this team agent.",
    )
    clear_target_agent: bool = Field(
        default=False,
        description=(
            "Set true to un-pin the target agent so the task runs via the team "
            "lead instead. Ignored when target_agent_id is also provided."
        ),
    )


class EditAutonomousTaskOutput(BaseModel):
    """Output model for edit_autonomous_task tool."""

    task: AutonomousTask = Field(
        description="The updated autonomous task configuration"
    )


class LeadEditAutonomousTask(LeadTool):
    """Tool to edit an existing team autonomous task."""

    name: str = "lead_edit_autonomous_task"
    description: str = (
        "Edit an existing team autonomous task. Only provided fields are "
        "updated; omitted fields keep their current values."
    )
    args_schema: ArgsSchema | None = EditAutonomousTaskInput

    @override
    async def _arun(
        self,
        task_id: str,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        prompt: str | None = None,
        enabled: bool | None = None,
        target_agent_id: str | None = None,
        clear_target_agent: bool = False,
        **kwargs: Any,
    ) -> EditAutonomousTaskOutput:
        context = self.get_context()
        assert context.team_id is not None

        # Only forward fields the caller actually provided so unset fields keep
        # their current values.
        candidates: dict[str, Any] = {
            "name": name,
            "description": description,
            "cron": cron,
            "prompt": prompt,
            "enabled": enabled,
            "target_agent_id": target_agent_id,
        }
        provided = {
            key: value for key, value in candidates.items() if value is not None
        }
        # Explicit un-pin: send target_agent_id=None (None can't be expressed via
        # the "drop None" filter above, so it needs a dedicated flag).
        if clear_target_agent and target_agent_id is None:
            provided["target_agent_id"] = None
        task_update = AutonomousUpdateRequest(**provided)
        updated_task = await update_autonomous_task(
            context.team_id, task_id, task_update
        )
        return EditAutonomousTaskOutput(task=updated_task)


lead_edit_autonomous_task_tool = LeadEditAutonomousTask()
