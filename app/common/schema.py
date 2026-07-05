import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse

from intentkit.core.agent.tool_registry import get_tool_catalog
from intentkit.models.agent import AGENT_TAG_CATEGORIES, Agent, AgentPublicInfo
from intentkit.utils.error import IntentKitAPIError

_AGENT_PUBLIC_TAGS_PAYLOAD = [
    {"value": tag.value, "category": category}
    for category, tags in AGENT_TAG_CATEGORIES.items()
    for tag in tags
]

logger = logging.getLogger(__name__)

# Create readonly router
schema_router = APIRouter()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


@schema_router.get("/schema/agent", tags=["Metadata"], operation_id="get_agent_schema")
async def get_agent_schema() -> JSONResponse:
    """Get the JSON schema for Agent model with all $ref references resolved.

    This function applies additional adaptations:
    - Populates the model enum from the in-memory LLM catalog (enabled models only)
    - Attaches the toolset catalog (x-catalog) filtered to what is available
      in the current deployment
    - Removes telegram-related fields

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the Agent model with application/json content type
    """
    schema = await Agent.get_json_schema()
    properties = schema.get("properties", {})

    # Remove telegram-related fields
    properties.pop("telegram_entrypoint_enabled", None)
    properties.pop("telegram_entrypoint_prompt", None)
    properties.pop("telegram_config", None)

    # Attach the toolset catalog so UIs can render a picker; the config
    # value itself is just a flat list of tool names.
    tools_property = properties.get("tools")
    if tools_property is not None:
        tools_property["x-catalog"] = get_tool_catalog(available_only=True)

    return JSONResponse(
        content=schema,
        media_type="application/json",
    )


@schema_router.get(
    "/schema/agent-public-info",
    tags=["Metadata"],
    operation_id="get_agent_public_info_schema",
)
async def get_agent_public_info_schema() -> JSONResponse:
    """Get the JSON schema for the AgentPublicInfo model.

    Used by team frontends when collecting public info as part of publishing
    an agent.
    """
    return JSONResponse(
        content=AgentPublicInfo.model_json_schema(),
        media_type="application/json",
    )


@schema_router.get(
    "/schema/agent-public-tags",
    tags=["Metadata"],
    operation_id="get_agent_public_tags",
)
async def get_agent_public_tags() -> JSONResponse:
    """List the predefined tag values usable when publishing an agent.

    Returned as a flat list of ``{value, category}`` entries in display order;
    the team frontend renders the labels client-side (capitalisation/i18n).
    """
    return JSONResponse(
        content=_AGENT_PUBLIC_TAGS_PAYLOAD,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@schema_router.get(
    "/tools/{tool}/schema.json",
    tags=["Metadata"],
    operation_id="get_tool_schema",
    responses={
        200: {"description": "Success"},
        404: {"description": "Tool not found"},
    },
)
async def get_tool_schema(
    tool: str = PathParam(..., description="Tool name", pattern="^[a-zA-Z0-9_-]+$"),
) -> JSONResponse:
    """Get the catalog entry for a specific toolset category.

    Synthesized from the in-code tool catalog (kept for compatibility with
    the old per-toolset schema.json files this endpoint used to serve).

    **Path Parameters:**
    * `tool` - Toolset category name

    **Returns:**
    * `JSONResponse` - The catalog entry with application/json content type

    **Raises:**
    * `IntentKitAPIError` - If the toolset is not found
    """
    catalog = get_tool_catalog()
    if tool not in catalog:
        raise IntentKitAPIError(404, "NotFound", "Tool schema not found")

    return JSONResponse(content=catalog[tool], media_type="application/json")


@schema_router.get(
    "/tools/{tool}/{icon_name}.{ext}",
    tags=["Metadata"],
    operation_id="get_tool_icon",
    responses={
        200: {"description": "Success"},
        404: {"description": "Tool icon not found"},
        400: {"description": "Invalid tool name or extension"},
    },
)
async def get_tool_icon(
    tool: str = PathParam(..., description="Tool name", pattern="^[a-zA-Z0-9_-]+$"),
    icon_name: str = PathParam(..., description="Icon name"),
    ext: str = PathParam(
        ..., description="Icon file extension", pattern="^(png|svg|jpg|jpeg|webp)$"
    ),
) -> FileResponse:
    """Get the icon for a specific tool.

    **Path Parameters:**
    * `tool` - Tool name
    * `icon_name` - Icon name
    * `ext` - Icon file extension (png or svg)

    **Returns:**
    * `FileResponse` - The icon file with appropriate content type

    **Raises:**
    * `IntentKitAPIError` - If the tool or icon is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "intentkit" / "tools"
    icon_path = base_path / tool / f"{icon_name}.{ext}"
    normalized_path = icon_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise IntentKitAPIError(400, "BadRequest", "Invalid tool name")

    if not normalized_path.exists():
        raise IntentKitAPIError(404, "NotFound", "Tool icon not found")

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
