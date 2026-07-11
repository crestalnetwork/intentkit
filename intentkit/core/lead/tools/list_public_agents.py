"""Tool to browse public agents across the platform."""

from __future__ import annotations

import asyncio
from typing import override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import get_followed_agent_ids, list_public_agents
from intentkit.core.lead.tools.base import LeadTool


class ListPublicAgentsInput(BaseModel):
    """Input model for list_public_agents tool."""

    search: str | None = Field(
        default=None,
        description="Optional case-insensitive substring to filter by name or description.",
    )
    limit: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum number of agents to return (default 30).",
    )


class PublicAgentSummary(BaseModel):
    """Summary of a public agent for browsing."""

    id: str
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    model: str | None = None
    owner: str | None = None
    followed: bool = Field(description="Whether this team already follows the agent.")


class ListPublicAgentsOutput(BaseModel):
    """Output model for list_public_agents tool."""

    agents: list[PublicAgentSummary] = Field(description="List of public agents")


class LeadListPublicAgents(LeadTool):
    """Tool to browse public agents from across the platform."""

    name: str = "lead_list_public_agents"
    description: str = (
        "Browse public agents from across the platform (not just this team). "
        "Use this to discover agents the team can follow. Each result shows "
        "whether this team already follows it. Follow useful ones with "
        "lead_follow_agent so they become available for delegation."
    )
    args_schema: ArgsSchema | None = ListPublicAgentsInput

    @override
    async def _arun(
        self, search: str | None = None, limit: int = 30
    ) -> ListPublicAgentsOutput:
        context = self.get_context()
        assert context.team_id is not None
        agents, followed_ids = await asyncio.gather(
            list_public_agents(search=search, limit=limit),
            get_followed_agent_ids(context.team_id),
        )
        summaries = [
            PublicAgentSummary(
                id=a.id,
                name=a.name,
                slug=a.slug,
                description=a.description,
                model=a.model,
                owner=a.owner,
                followed=a.id in followed_ids,
            )
            for a in agents
        ]
        return ListPublicAgentsOutput(agents=summaries)


lead_list_public_agents_tool = LeadListPublicAgents()
