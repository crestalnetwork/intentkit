"""Skill to update the lead agent's long-term memory."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill


class UpdateSelfMemoryInput(BaseModel):
    """Input model for lead_update_self_memory skill."""

    content: str = Field(
        ..., description="New memory content to merge into the lead agent's memory"
    )


class LeadUpdateSelfMemory(LeadSkill):
    """Skill to update the lead agent's long-term memory.

    Uses the standard memory merge mechanism (LLM-based consolidation).
    """

    name: str = "lead_update_self_memory"
    description: str = (
        "Add or update the lead agent's long-term memory. "
        "Provide new information to remember. "
        "Existing memory will be merged with the new content."
    )
    args_schema: ArgsSchema | None = UpdateSelfMemoryInput

    @override
    async def _arun(self, content: str, **kwargs: Any) -> str:
        from intentkit.core.memory import update_memory

        context = self.get_context()
        if not context.team_id:
            raise ToolException("No team_id in context")
        lead_agent_id = f"team-{context.team_id}"

        # update_memory invalidates the lead cache internally for team-* IDs,
        # so no explicit invalidate_lead_cache call is needed here.
        updated = await update_memory(lead_agent_id, content)
        return f"Lead agent memory updated successfully. Current memory:\n{updated}"


lead_update_self_memory_skill = LeadUpdateSelfMemory()
