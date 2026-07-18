"""Tool to list all agents in the team."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import get_team_agents
from intentkit.core.lead.tools.base import LeadTool
from intentkit.tools.base import NoArgsSchema


class AgentSummary(BaseModel):
    """Summary of an agent for listing."""

    id: str
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    model: str | None = None
    visibility: int | None = None
    owner: str | None = None
    updated_at: str | None = None
    created_at: str | None = None


class ListTeamAgentsOutput(BaseModel):
    """Output model for list_team_agents tool."""

    agents: list[AgentSummary] = Field(description="List of team agents")


class ListTeamAgents(LeadTool):
    """Tool to list all agents in the team."""

    name: str = "lead_list_team_agents"
    description: str = (
        "List all agents in the team with summary info: id, name, slug, "
        "description, model, visibility, owner, updated_at, created_at. "
        "Use lead_get_team_agent for the full config."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> ListTeamAgentsOutput:
        context = self.get_context()
        assert context.team_id is not None
        agents = await get_team_agents(context.team_id)
        summaries = [
            AgentSummary(
                id=a.id,
                name=a.name,
                slug=a.slug,
                description=a.description,
                model=a.model,
                visibility=a.visibility,
                owner=a.owner,
                updated_at=(a.updated_at.isoformat() if a.updated_at else None),
                created_at=(a.created_at.isoformat() if a.created_at else None),
            )
            for a in agents
        ]
        return ListTeamAgentsOutput(agents=summaries)


list_team_agents_tool = ListTeamAgents()
