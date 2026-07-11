"""Tool to create a new agent for the team."""

from __future__ import annotations

import logging
from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.agent.management import create_agent
from intentkit.core.lead.constants import SYSTEM_PROMPT_FIELD_DESCRIPTION
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.agent import AgentCreate, AgentVisibility

logger = logging.getLogger(__name__)


class CreateTeamAgentInput(BaseModel):
    """Input model for create_team_agent tool."""

    name: str = Field(description="Display name of the agent")
    slug: str = Field(description="URL-friendly slug", min_length=3, max_length=20)
    system_prompt: str = Field(
        description=SYSTEM_PROMPT_FIELD_DESCRIPTION, max_length=200000
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Short public summary of what the agent does; shown in agent "
            "listings and used to describe it when wired as a sub-agent."
        ),
    )
    model: str | None = Field(default=None, description="LLM model ID")
    temperature: float | None = Field(default=None, description="Temperature (0.0~2.0)")
    tools: list[str] | None = Field(
        default=None, description="List of enabled tool names"
    )
    search_internet: bool | None = Field(
        default=None, description="Enable internet search"
    )
    enable_todo: bool | None = Field(default=None, description="Enable todo list")
    enable_activity: bool | None = Field(
        default=None, description="Enable activity tools"
    )
    enable_post: bool | None = Field(default=None, description="Enable post tools")
    sub_agents: list[str] | None = Field(
        default=None, description="Sub-agent IDs or slugs"
    )
    sub_agent_prompt: str | None = Field(
        default=None, description="Instructions for sub-agents"
    )


class CreateTeamAgentOutput(BaseModel):
    """Output model for create_team_agent tool."""

    agent_id: str = Field(description="ID of the created agent")
    name: str | None = Field(description="Name of the created agent")
    message: str = Field(description="Success message")


class CreateTeamAgent(LeadTool):
    """Tool to create a new agent for the team."""

    name: str = "lead_create_team_agent"
    description: str = (
        "Create a new agent for the team. The agent will be directly deployed. "
        "Auto-sets team_id and owner from context, visibility defaults to TEAM."
    )
    args_schema: ArgsSchema | None = CreateTeamAgentInput

    @override
    async def _arun(
        self,
        name: str,
        system_prompt: str,
        slug: str,
        description: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[str] | None = None,
        search_internet: bool | None = None,
        enable_todo: bool | None = None,
        enable_activity: bool | None = None,
        enable_post: bool | None = None,
        sub_agents: list[str] | None = None,
        sub_agent_prompt: str | None = None,
        **kwargs: Any,
    ) -> CreateTeamAgentOutput:
        context = self.get_context()
        assert context.team_id is not None

        agent_data: dict[str, Any] = {
            "name": name,
            "slug": slug,
            "system_prompt": system_prompt,
        }
        if description is not None:
            agent_data["description"] = description
        if model is not None:
            agent_data["model"] = model
        if temperature is not None:
            agent_data["temperature"] = temperature
        if tools is not None:
            agent_data["tools"] = tools
        if search_internet is not None:
            agent_data["search_internet"] = search_internet
        if enable_todo is not None:
            agent_data["enable_todo"] = enable_todo
        if enable_activity is not None:
            agent_data["enable_activity"] = enable_activity
        if enable_post is not None:
            agent_data["enable_post"] = enable_post
        if sub_agents is not None:
            agent_data["sub_agents"] = sub_agents
        if sub_agent_prompt is not None:
            agent_data["sub_agent_prompt"] = sub_agent_prompt
        # Auto-set team fields
        agent_data["team_id"] = context.team_id  # team_id is stored as agent_id
        agent_data["owner"] = context.user_id
        agent_data["visibility"] = AgentVisibility.TEAM

        agent_create = AgentCreate.model_validate(agent_data)

        # Auto-generate avatar
        if not agent_create.picture:
            try:
                from intentkit.core.avatar import generate_avatar

                generated_avatar = await generate_avatar(agent_create.id, agent_create)
                if generated_avatar:
                    agent_create.picture = generated_avatar
            except Exception as e:
                logger.error("Failed to auto-generate avatar: %s", e)

        created_agent, _ = await create_agent(agent_create)

        # Invalidate lead cache so lead agent rebuilds sub-agents list
        from intentkit.core.lead.cache import invalidate_lead_cache

        invalidate_lead_cache(context.team_id)

        return CreateTeamAgentOutput(
            agent_id=created_agent.id,
            name=created_agent.name,
            message=f"Agent '{created_agent.name}' created and deployed successfully.",
        )


create_team_agent_tool = CreateTeamAgent()
