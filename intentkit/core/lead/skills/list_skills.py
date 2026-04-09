"""Skill to list available skills for agent configuration."""

from __future__ import annotations

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.skills.base import NoArgsSchema


class ListAvailableSkillsOutput(BaseModel):
    """Output model for list_available_skills skill."""

    skills_text: str = Field(
        description="Hierarchical text listing all available skills by category"
    )


class LeadListAvailableSkills(LeadSkill):
    """Skill to list all available skills organized by category."""

    name: str = "lead_list_available_skills"
    description: str = (
        "List all available skills organized by category. "
        "Returns skill names, descriptions, and category groupings "
        "for configuring agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> ListAvailableSkillsOutput:
        from intentkit.core.manager.service import get_skills_hierarchical_text

        skills_text = await asyncio.to_thread(get_skills_hierarchical_text)
        return ListAvailableSkillsOutput(skills_text=skills_text)


lead_list_available_skills_skill = LeadListAvailableSkills()
