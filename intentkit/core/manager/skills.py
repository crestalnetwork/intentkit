"""Manager skills for agent management operations."""

from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, SkipValidation

from intentkit.core.draft import (
    get_agent_latest_draft,
    update_agent_draft,
)
from intentkit.core.manager.service import (
    agent_draft_json_schema,
    get_latest_public_info,
)
from intentkit.models.agent import AgentPublicInfo, AgentUserInput
from intentkit.models.db import get_session
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.schema import resolve_schema_refs


class NoArgsSchema(BaseModel):
    """Empty schema for skills without arguments."""


class GetAgentLatestDraftSkill(IntentKitSkill):
    """Skill that retrieves the latest draft for the active agent."""

    name: str = "get_agent_latest_draft"
    description: str = "Fetch the latest draft for the current agent."
    args_schema: Annotated[ArgsSchema | None, SkipValidation()] = NoArgsSchema

    @property
    def category(self) -> str:
        return "manager"

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


class GetAgentLatestPublicInfoSkill(IntentKitSkill):
    """Skill that retrieves the latest public info for the active agent."""

    name: str = "get_agent_latest_public_info"
    description: str = "Fetch the latest public info for the current agent."
    args_schema: Annotated[ArgsSchema | None, SkipValidation()] = NoArgsSchema

    @property
    def category(self) -> str:
        return "manager"

    async def _arun(self) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        try:
            public_info = await get_latest_public_info(
                agent_id=context.agent_id,
                user_id=context.user_id,
            )
        except IntentKitAPIError as exc:
            if exc.key == "AgentNotFound":
                return (
                    "Agent not found. Please inform the user that only deployed agents "
                    "can update public info."
                )
            raise

        return json.dumps(public_info.model_dump(mode="json"), indent=2)


class UpdateAgentDraftSkill(IntentKitSkill):
    """Skill to update agent drafts with partial field updates."""

    name: str = "update_agent_draft"
    description: str = (
        "Update the latest draft for the current agent with only the specified fields. "
        "Only fields that are explicitly provided will be updated, leaving other fields unchanged. "
        "This is more efficient than override and reduces the risk of accidentally changing fields."
    )
    args_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "draft_update": agent_draft_json_schema(),
        },
        "required": ["draft_update"],
        "additionalProperties": False,
    }

    @property
    def category(self) -> str:
        return "manager"

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


class UpdatePublicInfoSkill(IntentKitSkill):
    """Skill to update the public info of an agent with partial field updates."""

    name: str = "update_public_info"
    description: str = (
        "Update the public info for a deployed agent with only the specified fields. "
        "Only fields that are explicitly provided will be updated, leaving other fields unchanged. "
        "This is more efficient than override and reduces the risk of accidentally changing fields. "
        "Always review the latest public info before making changes."
    )
    args_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "public_info_update": resolve_schema_refs(
                AgentPublicInfo.model_json_schema()
            ),
        },
        "required": ["public_info_update"],
        "additionalProperties": False,
    }

    @property
    def category(self) -> str:
        return "manager"

    async def _arun(self, **kwargs: Any) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        if "public_info_update" not in kwargs:
            raise ValueError("Missing required argument 'public_info_update'")

        # Ensure the agent exists and belongs to the current user
        await get_latest_public_info(agent_id=context.agent_id, user_id=context.user_id)

        public_info = AgentPublicInfo.model_validate(kwargs["public_info_update"])
        updated_agent = await public_info.update(context.agent_id)
        updated_public_info = AgentPublicInfo.model_validate(updated_agent)

        return json.dumps(updated_public_info.model_dump(mode="json"), indent=2)


# Shared skill instances to avoid repeated instantiation
get_agent_latest_draft_skill = GetAgentLatestDraftSkill()
get_agent_latest_public_info_skill = GetAgentLatestPublicInfoSkill()
update_agent_draft_skill = UpdateAgentDraftSkill()
update_public_info_skill = UpdatePublicInfoSkill()
