import importlib
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.agent import Agent
from intentkit.models.db import get_db
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Create readonly router
schema_router = APIRouter()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _is_skill_category_available(category: str) -> bool:
    """Check if a skill category is available based on its available() function.

    Args:
        category: The skill category name

    Returns:
        True if the skill is available, False otherwise
    """
    try:
        module = importlib.import_module(f"intentkit.skills.{category}")
        if hasattr(module, "available"):
            return module.available()
        # If no available function, assume it's available
        return True
    except Exception as e:
        logger.warning(f"Could not import skill category '{category}': {e}")
        return False


def _simplify_skill_schema(skill_schema: dict[str, Any]) -> dict[str, Any]:
    """Simplify skill schema to only keep enabled and states fields.

    Args:
        skill_schema: The original skill schema

    Returns:
        Simplified schema with only enabled, states, title, description, and type
    """
    simplified: dict[str, Any] = {}

    # Keep basic metadata
    for key in ["title", "description", "type"]:
        if key in skill_schema:
            simplified[key] = skill_schema[key]

    # Keep only enabled and states in properties
    original_properties = skill_schema.get("properties", {})
    if original_properties:
        simplified_properties: dict[str, Any] = {}
        if "enabled" in original_properties:
            simplified_properties["enabled"] = original_properties["enabled"]
        if "states" in original_properties:
            simplified_properties["states"] = original_properties["states"]
        if simplified_properties:
            simplified["properties"] = simplified_properties

    return simplified


@schema_router.get("/schema/agent", tags=["Schema"], operation_id="get_agent_schema")
async def get_agent_schema(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Get the JSON schema for Agent model with all $ref references resolved.

    For local mode, this function applies additional adaptations:
    - Filters out skill categories where available() returns False
    - Simplifies skill schemas to only keep enabled and states fields
    - Removes autonomous configuration
    - Removes telegram-related fields

    Updates the model property in the schema based on LLMModelInfo.get results.
    For each model in the enum list:
    - If the model is not found in LLMModelInfo, it remains unchanged
    - If the model is found but disabled (enabled=False), it is removed from the schema
    - If the model is found and enabled, its properties are updated based on the LLMModelInfo record

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the Agent model with application/json content type
    """
    schema = await Agent.get_json_schema(db)
    properties = schema.get("properties", {})

    # Remove autonomous field
    properties.pop("autonomous", None)

    # Remove telegram-related fields
    properties.pop("telegram_entrypoint_enabled", None)
    properties.pop("telegram_entrypoint_prompt", None)
    properties.pop("telegram_config", None)

    # Remove autonomous group from x-groups
    if "x-groups" in schema:
        schema["x-groups"] = [
            group for group in schema["x-groups"] if group.get("id") != "autonomous"
        ]

    # Filter and simplify skills
    skills_property = properties.get("skills", {})
    if skills_property and "properties" in skills_property:
        original_skills = skills_property["properties"]
        filtered_skills: dict[str, Any] = {}

        for category, skill_schema in original_skills.items():
            # Check if skill category is available
            if not _is_skill_category_available(category):
                logger.info(
                    f"Filtered out skill '{category}': not available in current config"
                )
                continue

            # Simplify the skill schema
            filtered_skills[category] = _simplify_skill_schema(skill_schema)

        skills_property["properties"] = filtered_skills

    return JSONResponse(
        content=schema,
        media_type="application/json",
    )


@schema_router.get(
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
    skill: str = PathParam(..., description="Skill name", pattern="^[a-zA-Z0-9_-]+$"),
) -> JSONResponse:
    """Get the JSON schema for a specific skill.

    **Path Parameters:**
    * `skill` - Skill name

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the skill with application/json content type

    **Raises:**
    * `IntentKitAPIError` - If the skill is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "intentkit" / "skills"
    schema_path = base_path / skill / "schema.json"
    normalized_path = schema_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise IntentKitAPIError(400, "BadRequest", "Invalid skill name")

    try:
        with open(normalized_path) as f:
            schema = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raise IntentKitAPIError(404, "NotFound", "Skill schema not found")

    return JSONResponse(content=schema, media_type="application/json")


@schema_router.get(
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
    skill: str = PathParam(..., description="Skill name", pattern="^[a-zA-Z0-9_-]+$"),
    icon_name: str = PathParam(..., description="Icon name"),
    ext: str = PathParam(
        ..., description="Icon file extension", pattern="^(png|svg|jpg|jpeg|webp)$"
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
    * `IntentKitAPIError` - If the skill or icon is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "intentkit" / "skills"
    icon_path = base_path / skill / f"{icon_name}.{ext}"
    normalized_path = icon_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise IntentKitAPIError(400, "BadRequest", "Invalid skill name")

    if not normalized_path.exists():
        raise IntentKitAPIError(404, "NotFound", "Skill icon not found")

    content_type = (
        "image/svg+xml"
        if ext == "svg"
        else "image/png"
        if ext in ["png"]
        else "image/webp"
        if ext in ["webp"]
        else "image/jpeg"
    )
    return FileResponse(normalized_path, media_type=content_type)
