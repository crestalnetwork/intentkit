"""Skill to get full config of a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill


class GetTeamAgentInput(BaseModel):
    """Input model for get_team_agent skill."""

    agent_id: str = Field(description="The ID of the agent to retrieve")


class GetTeamAgentOutput(BaseModel):
    """Output model for get_team_agent skill."""

    agent: dict[str, Any] = Field(description="Full agent configuration as JSON")


class GetTeamAgent(LeadSkill):
    """Skill to get full config of a team agent."""

    name: str = "lead_get_team_agent"
    description: str = (
        "Get the full configuration of a team agent by its ID. "
        "Returns all agent fields including skills, prompts, and settings."
    )
    args_schema: ArgsSchema | None = GetTeamAgentInput

    @override
    async def _arun(self, agent_id: str, **kwargs: Any) -> GetTeamAgentOutput:
        context = self.get_context()
        agent = await verify_agent_in_team(agent_id, context.agent_id)
        return GetTeamAgentOutput(agent=agent.model_dump(mode="json"))


get_team_agent_skill = GetTeamAgent()
