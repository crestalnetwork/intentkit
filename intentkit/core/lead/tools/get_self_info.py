"""Tool to get the lead agent's current configuration."""

from __future__ import annotations

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.constants import LEAD_DEFAULT_NAME, LEAD_DEFAULT_PERSONALITY
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.memory import Memory
from intentkit.models.team import Team
from intentkit.tools.base import NoArgsSchema


class GetSelfInfoOutput(BaseModel):
    """Output model for lead_get_self_info tool."""

    name: str = Field(description="Current lead agent name")
    avatar: str | None = Field(description="Current lead agent avatar URL")
    personality: str | None = Field(description="Current lead agent personality")
    memory: str | None = Field(description="Current lead agent long-term memory")


class LeadGetSelfInfo(LeadTool):
    """Tool to retrieve the lead agent's current configuration."""

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

        # Parallelize independent DB lookups; the lead's own memory is its
        # team-scope row.
        raw_config, memory = await asyncio.gather(
            Team.get_lead_agent_config(team_id),
            Memory.get(lead_agent_id, "team", team_id),
        )
        lead_config = raw_config or {}

        return GetSelfInfoOutput(
            name=lead_config.get("name", LEAD_DEFAULT_NAME),
            avatar=lead_config.get("avatar"),
            personality=lead_config.get("personality", LEAD_DEFAULT_PERSONALITY),
            memory=memory.content if memory else None,
        )


lead_get_self_info_tool = LeadGetSelfInfo()
