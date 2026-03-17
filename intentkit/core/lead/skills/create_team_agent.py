"""Skill to create a new agent for the team."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.agent.management import create_agent
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent import AgentCreate, AgentVisibility


class CreateTeamAgentInput(BaseModel):
    """Input model for create_team_agent skill."""

    name: str = Field(description="Display name of the agent")
    purpose: str | None = Field(
        default=None, description="Purpose or role of the agent"
    )
    personality: str | None = Field(default=None, description="Personality traits")
    principles: str | None = Field(default=None, description="Principles or values")
    model: str | None = Field(default=None, description="LLM model ID")
    prompt: str | None = Field(default=None, description="Base system prompt")
    prompt_append: str | None = Field(
        default=None, description="Additional system prompt"
    )
    temperature: float | None = Field(default=None, description="Temperature (0.0~2.0)")
    skills: dict[str, Any] | None = Field(
        default=None, description="Skill configurations"
    )
    slug: str | None = Field(default=None, description="URL-friendly slug")
    search_internet: bool | None = Field(
        default=None, description="Enable internet search"
    )
    super_mode: bool | None = Field(default=None, description="Enable super mode")
    enable_todo: bool | None = Field(default=None, description="Enable todo list")
    enable_activity: bool | None = Field(
        default=None, description="Enable activity skills"
    )
    enable_post: bool | None = Field(default=None, description="Enable post skills")
    enable_long_term_memory: bool | None = Field(
        default=None, description="Enable long-term memory"
    )
    sub_agents: list[str] | None = Field(
        default=None, description="Sub-agent IDs or slugs"
    )
    sub_agent_prompt: str | None = Field(
        default=None, description="Instructions for sub-agents"
    )
    short_term_memory_strategy: str | None = Field(
        default=None, description="'trim' or 'summarize'"
    )


class CreateTeamAgentOutput(BaseModel):
    """Output model for create_team_agent skill."""

    agent_id: str = Field(description="ID of the created agent")
    name: str | None = Field(description="Name of the created agent")
    message: str = Field(description="Success message")


class CreateTeamAgent(LeadSkill):
    """Skill to create a new agent for the team."""

    name: str = "lead_create_team_agent"
    description: str = (
        "Create a new agent for the team. The agent will be directly deployed "
        "(no draft flow). Auto-sets team_id and owner from context, visibility defaults to TEAM."
    )
    args_schema: ArgsSchema | None = CreateTeamAgentInput

    @override
    async def _arun(
        self,
        name: str,
        purpose: str | None = None,
        personality: str | None = None,
        principles: str | None = None,
        model: str | None = None,
        prompt: str | None = None,
        prompt_append: str | None = None,
        temperature: float | None = None,
        skills: dict[str, Any] | None = None,
        slug: str | None = None,
        search_internet: bool | None = None,
        super_mode: bool | None = None,
        enable_todo: bool | None = None,
        enable_activity: bool | None = None,
        enable_post: bool | None = None,
        enable_long_term_memory: bool | None = None,
        sub_agents: list[str] | None = None,
        sub_agent_prompt: str | None = None,
        short_term_memory_strategy: str | None = None,
        **kwargs: Any,
    ) -> CreateTeamAgentOutput:
        context = self.get_context()

        agent_data: dict[str, Any] = {"name": name}
        if purpose is not None:
            agent_data["purpose"] = purpose
        if personality is not None:
            agent_data["personality"] = personality
        if principles is not None:
            agent_data["principles"] = principles
        if model is not None:
            agent_data["model"] = model
        if prompt is not None:
            agent_data["prompt"] = prompt
        if prompt_append is not None:
            agent_data["prompt_append"] = prompt_append
        if temperature is not None:
            agent_data["temperature"] = temperature
        if skills is not None:
            agent_data["skills"] = skills
        if slug is not None:
            agent_data["slug"] = slug
        if search_internet is not None:
            agent_data["search_internet"] = search_internet
        if super_mode is not None:
            agent_data["super_mode"] = super_mode
        if enable_todo is not None:
            agent_data["enable_todo"] = enable_todo
        if enable_activity is not None:
            agent_data["enable_activity"] = enable_activity
        if enable_post is not None:
            agent_data["enable_post"] = enable_post
        if enable_long_term_memory is not None:
            agent_data["enable_long_term_memory"] = enable_long_term_memory
        if sub_agents is not None:
            agent_data["sub_agents"] = sub_agents
        if sub_agent_prompt is not None:
            agent_data["sub_agent_prompt"] = sub_agent_prompt
        if short_term_memory_strategy is not None:
            agent_data["short_term_memory_strategy"] = short_term_memory_strategy

        # Auto-set team fields
        agent_data["team_id"] = context.agent_id  # team_id is stored as agent_id
        agent_data["owner"] = context.user_id
        agent_data["visibility"] = AgentVisibility.TEAM

        agent_create = AgentCreate.model_validate(agent_data)
        created_agent, _ = await create_agent(agent_create)

        return CreateTeamAgentOutput(
            agent_id=created_agent.id,
            name=created_agent.name,
            message=f"Agent '{created_agent.name}' created and deployed successfully.",
        )


create_team_agent_skill = CreateTeamAgent()
