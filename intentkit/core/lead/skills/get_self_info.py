"""Skill to get the lead agent's current configuration."""

from __future__ import annotations

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.constants import LEAD_DEFAULT_NAME, LEAD_DEFAULT_PERSONALITY
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent_data import AgentData
from intentkit.models.team import Team
from intentkit.skills.base import NoArgsSchema


class GetSelfInfoOutput(BaseModel):
    """Output model for lead_get_self_info skill."""

    name: str = Field(description="Current lead agent name")
    avatar: str | None = Field(description="Current lead agent avatar URL")
    personality: str | None = Field(description="Current lead agent personality")
    memory: str | None = Field(description="Current lead agent long-term memory")


class LeadGetSelfInfo(LeadSkill):
    """Skill to retrieve the lead agent's current configuration."""

    name: str = "lead_get_self_info"
    description: str = (
        "Get the lead agent's current name, avatar, personality, and memory."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetSelfInfoOutput:
        context = self.get_context()
        team_id = context.team_id
        if not team_id:
            raise ToolException("No team_id in context")
        lead_agent_id = f"team-{team_id}"

        # Parallelize independent DB lookups
        raw_config, agent_data = await asyncio.gather(
            Team.get_lead_agent_config(team_id),
            AgentData.get(lead_agent_id),
        )
        lead_config = raw_config or {}

        return GetSelfInfoOutput(
            name=lead_config.get("name", LEAD_DEFAULT_NAME),
            avatar=lead_config.get("avatar"),
            personality=lead_config.get("personality", LEAD_DEFAULT_PERSONALITY),
            memory=agent_data.long_term_memory,
        )


lead_get_self_info_skill = LeadGetSelfInfo()
