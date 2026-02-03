"""Skills for managing agent drafts."""

from __future__ import annotations

import json
from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel

from intentkit.config.db import get_session
from intentkit.core.draft import (
    get_agent_latest_draft,
    update_agent_draft,
)
from intentkit.core.manager.service import agent_draft_json_schema
from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.models.agent import AgentUserInput
from intentkit.skills.base import NoArgsSchema


class GetAgentLatestDraftSkill(ManagerSkill):
    """Skill that retrieves the latest draft for the active agent."""

    name: str = "get_agent_latest_draft"
    description: str = "Fetch the latest draft for the current agent."
    # type: ignore[assignment]
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        async with get_session() as session:
            draft = await get_agent_latest_draft(
                agent_id=context.agent_id,
                user_id=context.user_id,
                db=session,
            )

        return json.dumps(draft.model_dump(mode="json"), indent=2)


class UpdateAgentDraftSchema(BaseModel):
    """Schema for updating an agent draft."""

    draft_update: AgentUserInput


class UpdateAgentDraftSkill(ManagerSkill):
    """Skill to update agent drafts with partial field updates."""

    name: str = "update_agent_draft"
    description: str = (
        "Update the latest draft for the current agent with only the specified fields. "
        "Only fields that are explicitly provided will be updated, leaving other fields unchanged. "
        "This is more efficient than override and reduces the risk of accidentally changing fields."
    )
    args_schema: ArgsSchema | None = {
        "type": "object",
        "properties": {
            "draft_update": agent_draft_json_schema(),
        },
        "required": ["draft_update"],
        "additionalProperties": False,
    }

    @override
    async def _arun(self, **kwargs: Any) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        if "draft_update" not in kwargs:
            raise ValueError("Missing required argument 'draft_update'")

        input_model = AgentUserInput.model_validate(kwargs["draft_update"])

        async with get_session() as session:
            draft = await update_agent_draft(
                agent_id=context.agent_id,
                user_id=context.user_id,
                input=input_model,
                db=session,
            )

        return json.dumps(draft.model_dump(mode="json"), indent=2)


# Shared skill instances
get_agent_latest_draft_skill = GetAgentLatestDraftSkill()
update_agent_draft_skill = UpdateAgentDraftSkill()
