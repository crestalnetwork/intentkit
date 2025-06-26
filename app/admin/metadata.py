import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import get_db
from models.llm import LLMModelInfo, LLMModelInfoTable, LLMProvider
from models.skill import Skill, SkillTable

# Create a readonly router for metadata endpoints
metadata_router_readonly = APIRouter(tags=["Metadata"])


class LLMModelInfoWithProviderName(LLMModelInfo):
    """LLM model information with provider display name."""

    provider_name: str


@metadata_router_readonly.get(
    "/metadata/skills",
    response_model=List[Skill],
    summary="Get all skills",
    description="Returns a list of all available skills in the system",
)
async def get_skills(db: AsyncSession = Depends(get_db)):
    """
    Get all skills available in the system.

    **Returns:**
    * `List[Skill]` - List of all skills
    """
    try:
        # Query all skills from the database
        stmt = select(SkillTable)
        result = await db.execute(stmt)
        skills = result.scalars().all()

        # Convert to Skill models
        return [Skill.model_validate(skill) for skill in skills]
    except Exception as e:
        logging.error(f"Error getting skills: {e}")
        raise


@metadata_router_readonly.get(
    "/metadata/llms",
    response_model=List[LLMModelInfoWithProviderName],
    summary="Get all LLM models",
    description="Returns a list of all available LLM models in the system",
)
async def get_llms(db: AsyncSession = Depends(get_db)):
    """
    Get all LLM models available in the system.

    **Returns:**
    * `List[LLMModelInfoWithProviderName]` - List of all LLM models with provider display names
    """
    try:
        # Query all LLM models from the database
        stmt = select(LLMModelInfoTable)
        result = await db.execute(stmt)
        models = result.scalars().all()

        # Convert to LLMModelInfoWithProviderName models
        result_models = []
        for model in models:
            model_info = LLMModelInfo.model_validate(model)
            # Convert provider string to LLMProvider enum if needed
            provider = (
                LLMProvider(model_info.provider)
                if isinstance(model_info.provider, str)
                else model_info.provider
            )
            result_models.append(
                LLMModelInfoWithProviderName(
                    **model_info.model_dump(),
                    provider_name=provider.display_name(),
                )
            )
        return result_models
    except Exception as e:
        logging.error(f"Error getting LLM models: {e}")
        raise
