"""Skill to get available LLMs."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.models.llm import LLMModelInfo
from intentkit.skills.base import NoArgsSchema


class LLMModelSummary(BaseModel):
    """Summary of an LLM model for agent configuration."""

    id: str = Field(description="Model ID used in agent config")
    name: str = Field(description="Display name")
    provider: str = Field(description="Provider name")
    context_length: int = Field(description="Max context length in tokens")
    output_length: int = Field(description="Max output length in tokens")
    intelligence: int = Field(description="Intelligence rating 1-5")
    speed: int = Field(description="Speed rating 1-5")
    input_price: str = Field(description="Price per 1M input tokens (USD)")
    output_price: str = Field(description="Price per 1M output tokens (USD)")
    supports_image_input: bool = Field(description="Whether supports image input")
    supports_audio_input: bool = Field(description="Whether supports audio input")
    supports_video_input: bool = Field(description="Whether supports video input")
    supports_file_input: bool = Field(description="Whether supports file input")
    reasoning_effort: str | None = Field(
        default=None, description="Reasoning effort level"
    )


class GetAvailableLLMsOutput(BaseModel):
    """Output model for get_available_llms skill."""

    models: list[LLMModelSummary] = Field(
        description="List of available LLM models with details"
    )


class LeadGetAvailableLLMs(LeadSkill):
    """Skill to retrieve list of available LLM models with details."""

    name: str = "lead_get_available_llms"
    description: str = (
        "Retrieve available LLM models with details including intelligence, speed, "
        "pricing, context length, and capabilities. Useful for choosing the right "
        "model when creating or updating agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetAvailableLLMsOutput:
        models = await LLMModelInfo.get_all()
        summaries = [
            LLMModelSummary(
                id=m.id,
                name=m.name,
                provider=m.provider.value,
                context_length=m.context_length,
                output_length=m.output_length,
                intelligence=m.intelligence,
                speed=m.speed,
                input_price=f"${m.input_price}/1M",
                output_price=f"${m.output_price}/1M",
                supports_image_input=m.supports_image_input,
                supports_audio_input=m.supports_audio_input,
                supports_video_input=m.supports_video_input,
                supports_file_input=m.supports_file_input,
                reasoning_effort=m.reasoning_effort,
            )
            for m in (models or [])
        ]
        return GetAvailableLLMsOutput(models=summaries)


lead_get_available_llms_skill = LeadGetAvailableLLMs()
