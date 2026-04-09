"""Skill to update the lead agent's own configuration."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.team import Team


class UpdateSelfInput(BaseModel):
    """Input model for lead_update_self skill."""

    name: str | None = Field(
        default=None, description="New display name (max 50 chars)"
    )
    avatar: str | None = Field(default=None, description="New avatar URL")
    personality: str | None = Field(
        default=None, description="New personality description"
    )


class UpdateSelfOutput(BaseModel):
    """Output model for lead_update_self skill."""

    message: str = Field(description="Success message")
    updated_fields: list[str] = Field(description="List of fields that were updated")


class LeadUpdateSelf(LeadSkill):
    """Skill to update the lead agent's name, avatar, or personality.

    Changes take effect after the lead agent cache is invalidated.
    """

    name: str = "lead_update_self"
    description: str = (
        "Update the lead agent's name, avatar, or personality. "
        "Only provide the fields you want to change."
    )
    args_schema: ArgsSchema | None = UpdateSelfInput

    @override
    async def _arun(
        self,
        name: str | None = None,
        avatar: str | None = None,
        personality: str | None = None,
        **kwargs: Any,
    ) -> UpdateSelfOutput:
        context = self.get_context()
        team_id = context.team_id
        if not team_id:
            raise ToolException("No team_id in context")

        updates: dict[str, Any] = {}
        updated_fields: list[str] = []

        if name is not None:
            updates["name"] = name[:50]
            updated_fields.append("name")
        if avatar is not None:
            updates["avatar"] = avatar[:1000] if avatar else avatar
            updated_fields.append("avatar")
        if personality is not None:
            updates["personality"] = personality[:20000]
            updated_fields.append("personality")

        if not updates:
            return UpdateSelfOutput(
                message="No fields provided to update.",
                updated_fields=[],
            )

        await Team.update_lead_agent_config(team_id, updates)

        # Invalidate lead cache so changes take effect
        from intentkit.core.lead.cache import invalidate_lead_cache

        invalidate_lead_cache(team_id)

        return UpdateSelfOutput(
            message=f"Lead agent updated: {', '.join(updated_fields)}.",
            updated_fields=updated_fields,
        )


lead_update_self_skill = LeadUpdateSelf()
