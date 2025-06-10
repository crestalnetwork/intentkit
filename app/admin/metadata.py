import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import get_db
from models.llm import LLMModelInfo, LLMModelInfoTable
from models.skill import Skill, SkillTable

# Create a readonly router for metadata endpoints
metadata_router_readonly = APIRouter(tags=["Metadata"])


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
    response_model=List[LLMModelInfo],
    summary="Get all LLM models",
    description="Returns a list of all available LLM models in the system",
)
async def get_llms(db: AsyncSession = Depends(get_db)):
    """
    Get all LLM models available in the system.

    **Returns:**
    * `List[LLMModelInfo]` - List of all LLM models
    """
    try:
        # Query all LLM models from the database
        stmt = select(LLMModelInfoTable)
        result = await db.execute(stmt)
        models = result.scalars().all()

        # Convert to LLMModelInfo models
        return [LLMModelInfo.model_validate(model) for model in models]
    except Exception as e:
        logging.error(f"Error getting LLM models: {e}")
        raise
