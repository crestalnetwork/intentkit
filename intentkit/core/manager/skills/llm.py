from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.models.llm import LLMModelInfo
from intentkit.skills.base import NoArgsSchema


class GetAvailableLLMsOutput(BaseModel):
    """Output model for get_available_llms skill."""

    models: list[str] = Field(description="List of available LLM model IDs")


class GetAvailableLLMs(ManagerSkill):
    """Skill to retrieve list of available LLM models."""

    name: str = "get_available_llms"
    description: str = (
        "Retrieve a list of available LLM model IDs that can be used for agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetAvailableLLMsOutput:
        """Retrieve available LLM models."""
        models = await LLMModelInfo.get_all()
        model_ids = [m.id for m in models] if models else []
        return GetAvailableLLMsOutput(models=model_ids)


# Shared skill instances
get_available_llms_skill = GetAvailableLLMs()
