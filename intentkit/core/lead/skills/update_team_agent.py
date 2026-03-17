"""Skill to update (patch) a team agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.agent.management import patch_agent
from intentkit.core.lead.service import verify_agent_in_team
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.agent import AgentUpdate


class UpdateTeamAgentInput(BaseModel):
    """Input model for update_team_agent skill."""

    agent_id: str = Field(description="The ID of the agent to update")
    name: str | None = Field(default=None, description="Display name")
    purpose: str | None = Field(default=None, description="Purpose or role")
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
    visibility: int | None = Field(
        default=None, description="Visibility: PRIVATE(0), TEAM(10), PUBLIC(20)"
    )
    telegram_entrypoint_enabled: bool | None = Field(
        default=None, description="Enable telegram bot"
    )
    telegram_entrypoint_prompt: str | None = Field(
        default=None, description="Extra prompt for telegram"
    )
    telegram_config: dict[str, Any] | None = Field(
        default=None, description="Telegram config"
    )
    discord_entrypoint_enabled: bool | None = Field(
        default=None, description="Enable discord bot"
    )
    discord_config: dict[str, Any] | None = Field(
        default=None, description="Discord config"
    )
    xmtp_entrypoint_prompt: str | None = Field(
        default=None, description="Extra prompt for XMTP"
    )


class UpdateTeamAgentOutput(BaseModel):
    """Output model for update_team_agent skill."""

    agent_id: str = Field(description="ID of the updated agent")
    message: str = Field(description="Success message")


class UpdateTeamAgent(LeadSkill):
    """Skill to update (patch) a team agent. Changes are directly deployed."""

    name: str = "lead_update_team_agent"
    description: str = (
        "Update a team agent with partial changes. Only provided fields will be updated. "
        "Changes are directly deployed (no draft flow). "
        "The update function is efficient and safe, only updating fields you explicitly provide."
    )
    args_schema: ArgsSchema | None = UpdateTeamAgentInput

    @override
    async def _arun(
        self,
        agent_id: str,
        name: str | None = None,
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
        visibility: int | None = None,
        telegram_entrypoint_enabled: bool | None = None,
        telegram_entrypoint_prompt: str | None = None,
        telegram_config: dict[str, Any] | None = None,
        discord_entrypoint_enabled: bool | None = None,
        discord_config: dict[str, Any] | None = None,
        xmtp_entrypoint_prompt: str | None = None,
        **kwargs: Any,
    ) -> UpdateTeamAgentOutput:
        context = self.get_context()
        await verify_agent_in_team(agent_id, context.agent_id)

        # Build update data from explicitly provided fields
        update_data: dict[str, Any] = {}
        local_vars = {
            "name": name,
            "purpose": purpose,
            "personality": personality,
            "principles": principles,
            "model": model,
            "prompt": prompt,
            "prompt_append": prompt_append,
            "temperature": temperature,
            "skills": skills,
            "slug": slug,
            "search_internet": search_internet,
            "super_mode": super_mode,
            "enable_todo": enable_todo,
            "enable_activity": enable_activity,
            "enable_post": enable_post,
            "enable_long_term_memory": enable_long_term_memory,
            "sub_agents": sub_agents,
            "sub_agent_prompt": sub_agent_prompt,
            "short_term_memory_strategy": short_term_memory_strategy,
            "visibility": visibility,
            "telegram_entrypoint_enabled": telegram_entrypoint_enabled,
            "telegram_entrypoint_prompt": telegram_entrypoint_prompt,
            "telegram_config": telegram_config,
            "discord_entrypoint_enabled": discord_entrypoint_enabled,
            "discord_config": discord_config,
            "xmtp_entrypoint_prompt": xmtp_entrypoint_prompt,
        }
        for key, value in local_vars.items():
            if value is not None:
                update_data[key] = value

        # AgentUpdate has name with default=None, so it's safe to omit
        agent_update = AgentUpdate.model_validate(update_data)
        updated_agent, _ = await patch_agent(agent_id, agent_update)

        return UpdateTeamAgentOutput(
            agent_id=updated_agent.id,
            message=f"Agent '{updated_agent.name}' updated and deployed successfully.",
        )


update_team_agent_skill = UpdateTeamAgent()
