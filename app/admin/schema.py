import json
import logging
from pathlib import Path
from typing import Dict

import jsonref
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.config import config
from models.db import get_db, get_session
from models.llm import LLMModelInfo
from models.skill import SkillTable

logger = logging.getLogger(__name__)

# Create readonly router
schema_router_readonly = APIRouter()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Path to agent schema
AGENT_SCHEMA_PATH = PROJECT_ROOT / "models" / "agent_schema.json"

# Skills that require agent owner to provide API keys (should be excluded from auto-generation)
AGENT_OWNER_API_KEY_SKILLS = {
    "dune_analytics",
    "dapplooker",
    "cryptocompare",
    "aixbt",
}


async def get_agent_schema_with_admin_config(
    db: AsyncSession = None, filter_owner_api_skills: bool = False
) -> Dict:
    """Get the JSON schema for Agent model with all $ref references resolved.

    This is the shared function that handles admin configuration filtering
    for both the API endpoint and agent generation.

    Args:
        db: Database session (optional, will create if not provided)
        filter_owner_api_skills: Whether to filter out skills that require agent owner API keys

    Returns:
        Dict containing the complete JSON schema for the Agent model
    """
    # Get database session if not provided
    if db is None:
        async with get_session() as session:
            return await get_agent_schema_with_admin_config(
                session, filter_owner_api_skills
            )

    base_uri = f"file://{AGENT_SCHEMA_PATH}"
    with open(AGENT_SCHEMA_PATH) as f:
        schema = jsonref.load(f, base_uri=base_uri, proxies=False, lazy_load=False)

        # Get the model property from the schema
        model_property = schema.get("properties", {}).get("model", {})

        if config.admin_llm_skill_control:
            # Process model property
            if model_property and "enum" in model_property:
                # Get the original lists
                enum_values = model_property.get("enum", [])
                enum_titles = model_property.get("x-enum-title", [])
                enum_categories = model_property.get("x-enum-category", [])
                enum_support_skill = model_property.get("x-support-skill", [])

                # Create new lists for the updated values
                new_enum = []
                new_enum_title = []
                new_enum_category = []
                new_enum_support_skill = []

                # Process each model in the enum
                for i, model_id in enumerate(enum_values):
                    # Try to get model info from LLMModelInfo
                    model_info = await LLMModelInfo.get(model_id)

                    if model_info is None:
                        # If model not found, keep it as is
                        new_enum.append(model_id)
                        if i < len(enum_titles):
                            new_enum_title.append(enum_titles[i])
                        if i < len(enum_categories):
                            new_enum_category.append(enum_categories[i])
                        if i < len(enum_support_skill):
                            new_enum_support_skill.append(enum_support_skill[i])
                    elif model_info.enabled:
                        # If model is enabled, update it with the latest info
                        new_enum.append(model_id)
                        if i < len(enum_titles):
                            new_enum_title.append(enum_titles[i])
                        if i < len(enum_categories):
                            new_enum_category.append(enum_categories[i])
                        if i < len(enum_support_skill):
                            new_enum_support_skill.append(
                                model_info.supports_skill_calls
                            )
                    # If model is disabled, skip it (don't add to new lists)

                # Update the schema with the new lists
                model_property["enum"] = new_enum
                model_property["x-enum-title"] = new_enum_title
                model_property["x-enum-category"] = new_enum_category
                model_property["x-support-skill"] = new_enum_support_skill

                # If the default model is not in the new enum, update it if possible
                if (
                    "default" in model_property
                    and model_property["default"] not in new_enum
                    and new_enum
                ):
                    model_property["default"] = new_enum[0]

            # Process skills property
            skills_property = schema.get("properties", {}).get("skills", {})
            skills_properties = skills_property.get("properties", {})

            if skills_properties:
                # Load all skills from the database
                # Query all skills grouped by category with enabled status
                stmt = select(
                    SkillTable.category,
                    func.bool_or(SkillTable.enabled).label("any_enabled"),
                ).group_by(SkillTable.category)
                result = await db.execute(stmt)
                category_status = {row.category: row.any_enabled for row in result}

                # Query all skills with their price levels for adding x-price-level fields
                skills_stmt = select(
                    SkillTable.category,
                    SkillTable.config_name,
                    SkillTable.price_level,
                    SkillTable.enabled,
                ).where(SkillTable.enabled)
                skills_result = await db.execute(skills_stmt)
                skills_data = {}
                category_price_levels = {}

                for row in skills_result:
                    if row.category not in skills_data:
                        skills_data[row.category] = {}
                        category_price_levels[row.category] = []

                    if row.config_name:
                        skills_data[row.category][row.config_name] = row.price_level

                    if row.price_level is not None:
                        category_price_levels[row.category].append(row.price_level)

                # Calculate average price levels for categories
                category_avg_price_levels = {}
                for category, price_levels in category_price_levels.items():
                    if price_levels:
                        avg_price_level = int(sum(price_levels) / len(price_levels))
                        category_avg_price_levels[category] = avg_price_level

                # Create a copy of keys to avoid modifying during iteration
                skill_keys = list(skills_properties.keys())

                # Process each skill in the schema
                for skill_category in skill_keys:
                    if skill_category not in category_status:
                        # If category not found in database, remove it from schema
                        skills_properties.pop(skill_category, None)
                    elif not category_status[skill_category]:
                        # If category exists but all skills are disabled, remove it
                        skills_properties.pop(skill_category, None)
                    elif (
                        filter_owner_api_skills
                        and skill_category in AGENT_OWNER_API_KEY_SKILLS
                    ):
                        # If filtering owner API skills and this skill requires it, remove it
                        skills_properties.pop(skill_category, None)
                        logger.info(
                            f"Filtered out skill '{skill_category}' from auto-generation: requires agent owner API key"
                        )
                    else:
                        # Add x-avg-price-level to category level
                        if skill_category in category_avg_price_levels:
                            skills_properties[skill_category]["x-avg-price-level"] = (
                                category_avg_price_levels[skill_category]
                            )

                        # Add x-price-level to individual skill states
                        if skill_category in skills_data:
                            skill_states = (
                                skills_properties[skill_category]
                                .get("properties", {})
                                .get("states", {})
                                .get("properties", {})
                            )
                            for state_name, state_config in skill_states.items():
                                if (
                                    state_name in skills_data[skill_category]
                                    and skills_data[skill_category][state_name]
                                    is not None
                                ):
                                    state_config["x-price-level"] = skills_data[
                                        skill_category
                                    ][state_name]

        # Log the changes for debugging
        logger.debug(
            f"Schema processed with LLM and skill controls enabled: {config.admin_llm_skill_control}, "
            f"filtered owner API skills: {filter_owner_api_skills}"
        )

        return schema


@schema_router_readonly.get(
    "/schema/agent", tags=["Schema"], operation_id="get_agent_schema"
)
async def get_agent_schema(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Get the JSON schema for Agent model with all $ref references resolved.

    Updates the model property in the schema based on LLMModelInfo.get results.
    For each model in the enum list:
    - If the model is not found in LLMModelInfo, it remains unchanged
    - If the model is found but disabled (enabled=False), it is removed from the schema
    - If the model is found and enabled, its properties are updated based on the LLMModelInfo record

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the Agent model with application/json content type
    """
    return JSONResponse(
        content=await get_agent_schema_with_admin_config(db),
        media_type="application/json",
    )


@schema_router_readonly.get(
    "/skills/{skill}/schema.json",
    tags=["Schema"],
    operation_id="get_skill_schema",
    responses={
        200: {"description": "Success"},
        404: {"description": "Skill not found"},
        400: {"description": "Invalid skill name"},
    },
)
async def get_skill_schema(
    skill: str = PathParam(..., description="Skill name", regex="^[a-zA-Z0-9_-]+$"),
) -> JSONResponse:
    """Get the JSON schema for a specific skill.

    **Path Parameters:**
    * `skill` - Skill name

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the skill with application/json content type

    **Raises:**
    * `HTTPException` - If the skill is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "skills"
    schema_path = base_path / skill / "schema.json"
    normalized_path = schema_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise HTTPException(status_code=400, detail="Invalid skill name")

    try:
        with open(normalized_path) as f:
            schema = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="Skill schema not found")

    return JSONResponse(content=schema, media_type="application/json")


@schema_router_readonly.get(
    "/skills/{skill}/{icon_name}.{ext}",
    tags=["Schema"],
    operation_id="get_skill_icon",
    responses={
        200: {"description": "Success"},
        404: {"description": "Skill icon not found"},
        400: {"description": "Invalid skill name or extension"},
    },
)
async def get_skill_icon(
    skill: str = PathParam(..., description="Skill name", regex="^[a-zA-Z0-9_-]+$"),
    icon_name: str = PathParam(..., description="Icon name"),
    ext: str = PathParam(
        ..., description="Icon file extension", regex="^(png|svg|jpg|jpeg)$"
    ),
) -> FileResponse:
    """Get the icon for a specific skill.

    **Path Parameters:**
    * `skill` - Skill name
    * `icon_name` - Icon name
    * `ext` - Icon file extension (png or svg)

    **Returns:**
    * `FileResponse` - The icon file with appropriate content type

    **Raises:**
    * `HTTPException` - If the skill or icon is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "skills"
    icon_path = base_path / skill / f"{icon_name}.{ext}"
    normalized_path = icon_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise HTTPException(status_code=400, detail="Invalid skill name")

    if not normalized_path.exists():
        raise HTTPException(status_code=404, detail="Skill icon not found")

    content_type = (
        "image/svg+xml"
        if ext == "svg"
        else "image/png"
        if ext in ["png"]
        else "image/jpeg"
    )
    return FileResponse(normalized_path, media_type=content_type)
