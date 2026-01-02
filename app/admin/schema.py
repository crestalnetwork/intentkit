import json
import logging
from pathlib import Path

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


@schema_router.get("/schema/agent", tags=["Schema"], operation_id="get_agent_schema")
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
        content=await Agent.get_json_schema(db),
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
