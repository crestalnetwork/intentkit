"""Skills for managing agent public info."""

from __future__ import annotations

import json
from typing import Annotated, Any, override

from langchain_core.tools import ArgsSchema
from pydantic import SkipValidation

from intentkit.core.manager.service import get_latest_public_info
from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.core.manager.skills.common import NoArgsSchema
from intentkit.models.agent import AgentPublicInfo
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.schema import resolve_schema_refs


class GetAgentLatestPublicInfoSkill(ManagerSkill):
    """Skill that retrieves the latest public info for the active agent."""

    name: str = "get_agent_latest_public_info"
    description: str = "Fetch the latest public info for the current agent."
    # type: ignore[assignment]
    args_schema: Annotated[ArgsSchema | None, SkipValidation()] = NoArgsSchema

    @override
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


class UpdatePublicInfoSkill(ManagerSkill):
    """Skill to update the public info of an agent with partial field updates."""

    name: str = "update_public_info"
    description: str = (
        "Update the public info for a deployed agent with only the specified fields. "
        "Only fields that are explicitly provided will be updated, leaving other fields unchanged. "
        "This is more efficient than override and reduces the risk of accidentally changing fields. "
        "Always review the latest public info before making changes."
    )
    args_schema: dict[str, Any] = {  # type: ignore[assignment]
        "type": "object",
        "properties": {
            "public_info_update": resolve_schema_refs(
                AgentPublicInfo.model_json_schema()
            ),
        },
        "required": ["public_info_update"],
        "additionalProperties": False,
    }

    @override
    async def _arun(self, **kwargs: Any) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        if "public_info_update" not in kwargs:
            raise ValueError("Missing required argument 'public_info_update'")

        # Ensure the agent exists and belongs to the current user
        _ = await get_latest_public_info(
            agent_id=context.agent_id, user_id=context.user_id
        )

        public_info = AgentPublicInfo.model_validate(kwargs["public_info_update"])
        updated_agent = await public_info.update(context.agent_id)
        updated_public_info = AgentPublicInfo.model_validate(updated_agent)

        return json.dumps(updated_public_info.model_dump(mode="json"), indent=2)


# Shared skill instances
get_agent_latest_public_info_skill = GetAgentLatestPublicInfoSkill()
update_public_info_skill = UpdatePublicInfoSkill()
