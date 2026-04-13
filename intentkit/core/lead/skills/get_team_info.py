"""Skill to get team info and members."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import get_team_with_members
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.skills.base import NoArgsSchema


class GetTeamInfoOutput(BaseModel):
    """Output model for get_team_info skill."""

    team: dict[str, Any] = Field(description="Team info with members")


class GetTeamInfo(LeadSkill):
    """Skill to get team info and members."""

    name: str = "lead_get_team_info"
    description: str = (
        "Get team information including name, avatar, and all members with their roles."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetTeamInfoOutput:
        context = self.get_context()
        assert context.team_id is not None
        team_info = await get_team_with_members(context.team_id)
        return GetTeamInfoOutput(team=team_info)


get_team_info_skill = GetTeamInfo()
