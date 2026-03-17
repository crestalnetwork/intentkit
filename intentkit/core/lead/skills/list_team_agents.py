"""Skill to list all agents in the team."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import get_team_agents
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.skills.base import NoArgsSchema


class AgentSummary(BaseModel):
    """Summary of an agent for listing."""

    id: str
    name: str | None = None
    slug: str | None = None
    purpose: str | None = None
    model: str | None = None
    visibility: int | None = None
    owner: str | None = None
    deployed_at: str | None = None
    created_at: str | None = None


class ListTeamAgentsOutput(BaseModel):
    """Output model for list_team_agents skill."""

    agents: list[AgentSummary] = Field(description="List of team agents")


class ListTeamAgents(LeadSkill):
    """Skill to list all agents in the team."""

    name: str = "lead_list_team_agents"
    description: str = "List all agents in the team with summary info: id, name, slug, purpose, model, visibility, owner, deployed_at, created_at."
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> ListTeamAgentsOutput:
        context = self.get_context()
        agents = await get_team_agents(context.agent_id)
        summaries = [
            AgentSummary(
                id=a.id,
                name=a.name,
                slug=a.slug,
                purpose=a.purpose,
                model=a.model,
                visibility=a.visibility,
                owner=a.owner,
                deployed_at=(a.deployed_at.isoformat() if a.deployed_at else None),
                created_at=(a.created_at.isoformat() if a.created_at else None),
            )
            for a in agents
        ]
        return ListTeamAgentsOutput(agents=summaries)


list_team_agents_skill = ListTeamAgents()
