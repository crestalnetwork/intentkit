"""Skill to get available LLMs."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.llm import LLMModelInfo
from intentkit.skills.base import NoArgsSchema


class GetAvailableLLMsOutput(BaseModel):
    """Output model for get_available_llms skill."""

    models: list[str] = Field(description="List of available LLM model IDs")


class LeadGetAvailableLLMs(LeadSkill):
    """Skill to retrieve list of available LLM models."""

    name: str = "lead_get_available_llms"
    description: str = (
        "Retrieve a list of available LLM model IDs that can be used for agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetAvailableLLMsOutput:
        models = await LLMModelInfo.get_all()
        model_ids = [m.id for m in models] if models else []
        return GetAvailableLLMsOutput(models=model_ids)


lead_get_available_llms_skill = LeadGetAvailableLLMs()
