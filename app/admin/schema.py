import json
import logging
from pathlib import Path

import jsonref
from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Create readonly router
schema_router_readonly = APIRouter()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Path to agent schema
AGENT_SCHEMA_PATH = PROJECT_ROOT / "models" / "agent_schema.json"


@schema_router_readonly.get(
    "/schema/agent", tags=["Schema"], operation_id="get_agent_schema"
)
async def get_agent_schema() -> JSONResponse:
    """Get the JSON schema for Agent model with all $ref references resolved.

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the Agent model with application/json content type
    """
    base_uri = f"file://{AGENT_SCHEMA_PATH}"
    with open(AGENT_SCHEMA_PATH) as f:
        schema = jsonref.load(f, base_uri=base_uri, proxies=False, lazy_load=False)
        return JSONResponse(
            content=schema,
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
