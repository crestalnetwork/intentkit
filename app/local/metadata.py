import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db
from intentkit.models.llm import LLMModelInfo, LLMProvider

# Create a readonly router for metadata endpoints
metadata_router = APIRouter(tags=["Metadata"])


class LLMModelInfoWithProviderName(LLMModelInfo):
    """LLM model information with provider display name."""

    provider_name: str


@metadata_router.get(
    "/metadata/llms",
    response_model=list[LLMModelInfoWithProviderName],
    summary="Get all LLM models",
    description="Returns a list of all available LLM models in the system",
)
async def get_llms(db: AsyncSession = Depends(get_db)):
    """
    Get all LLM models available in the system.

    **Returns:**
    * `list[LLMModelInfoWithProviderName]` - List of all LLM models with provider display names
    """
    try:
        result_models = []
        for model_info in await LLMModelInfo.get_all(db):
            provider = LLMProvider(model_info.provider)
            result_models.append(
                LLMModelInfoWithProviderName(
                    **model_info.model_dump(),
                    provider_name=provider.display_name(),
                )
            )
        return result_models
    except Exception as e:
        logging.error("Error getting LLM models: %s", e)
        raise
