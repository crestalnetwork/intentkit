import asyncio
import logging
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Path,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db, get_session
from intentkit.core.agent import (
    backfill_agent_avatar,
    create_agent,
    get_agent_by_id_or_slug,
    override_agent,
    patch_agent,
)
from intentkit.core.agent import (
    get_agent as get_agent_by_id,
)
from intentkit.core.agent.publish import (
    ensure_not_referenced_by_public_agent,
    ensure_sub_agents_public,
    is_public_visibility,
)
from intentkit.core.lead import invalidate_lead_cache
from intentkit.core.template import render_agent
from intentkit.models.agent import (
    Agent,
    AgentCreate,
    AgentResponse,
    AgentTable,
    AgentUpdate,
)
from intentkit.models.agent_data import AgentData, AgentDataTable
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.yaml import safe_load

from app.common.upload import validate_and_store_image

agent_router = APIRouter()

logger = logging.getLogger(__name__)


@agent_router.post(
    "/agents",
    tags=["Agent"],
    status_code=201,
    operation_id="create_agent",
    responses={
        201: {"description": "Agent created successfully"},
    },
    summary="Create Agent",
)
async def create_agent_endpoint(
    background_tasks: BackgroundTasks,
    agent: AgentUpdate = Body(AgentUpdate, description="Agent user input"),
) -> Response:
    """Create a new agent.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `AgentResponse` - Created agent configuration with additional processed data

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid agent ID format or agent ID already exists
        - 500: Database error
    """
    new_agent = AgentCreate.model_validate(agent)
    new_agent.owner = "system"
    new_agent.team_id = "system"

    latest_agent, agent_data = await create_agent(new_agent)
    invalidate_lead_cache(new_agent.team_id or "system")

    if not latest_agent.picture:
        background_tasks.add_task(backfill_agent_avatar, latest_agent.id)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header and appropriate status code
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
        status_code=201,
    )


@agent_router.put(
    "/agents/{agent_id}",
    tags=["Agent"],
    status_code=200,
    operation_id="override_agent",
    summary="Override Agent",
)
async def override_agent_endpoint(
    background_tasks: BackgroundTasks,
    agent_id: str = Path(..., description="ID of the agent to update"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent update configuration"),
) -> Response:
    """Override an existing agent.

    Use input to override agent configuration. If some fields are not provided, they will be reset to default values.

    **Path Parameters:**
    * `agent_id` - ID of the agent to update

    **Request Body:**
    * `agent` - Agent update configuration

    **Returns:**
    * `AgentResponse` - Updated agent configuration with additional processed data

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid agent ID format
        - 404: Agent not found
        - 500: Database error
    """
    picture_provided = "picture" in agent.model_fields_set

    latest_agent, agent_data = await override_agent(agent_id, agent)

    if not picture_provided:
        background_tasks.add_task(backfill_agent_avatar, agent_id)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@agent_router.patch(
    "/agents/{agent_id}",
    tags=["Agent"],
    status_code=200,
    operation_id="patch_agent",
    summary="Patch Agent",
)
async def patch_agent_endpoint(
    background_tasks: BackgroundTasks,
    agent_id: str = Path(..., description="ID of the agent to patch"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent patch configuration"),
) -> Response:
    """Patch an existing agent with partial updates.

    Use input to partially update agent configuration. Only the fields that are provided will be updated,
    other fields will remain unchanged.

    **Path Parameters:**
    * `agent_id` - ID of the agent to patch

    **Request Body:**
    * `agent` - Agent patch configuration (only include fields to update)

    **Returns:**
    * `AgentResponse` - Updated agent configuration with additional processed data

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid agent ID format
        - 404: Agent not found
        - 500: Database error
    """
    update_fields = agent.model_dump(exclude_unset=True)
    picture_explicitly_set = "picture" in update_fields

    latest_agent, agent_data = await patch_agent(agent_id, agent)

    # backfill_agent_avatar re-reads the row and short-circuits if picture is
    # already set, so we can schedule unconditionally whenever the caller
    # didn't hand us one and skip a hot-path DB round-trip here.
    if not picture_explicitly_set:
        background_tasks.add_task(backfill_agent_avatar, agent_id)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@agent_router.get(
    "/agents",
    tags=["Agent"],
    operation_id="get_agents",
)
async def get_agents(db: AsyncSession = Depends(get_db)) -> list[AgentResponse]:
    """Get all agents with their quota information.

    By default, archived agents (with archived_at set) are excluded.

    **Returns:**
    * `list[AgentResponse]` - List of agents with their quota information and additional processed data
    """
    # Query all non-archived agents
    agents = (
        await db.scalars(
            select(AgentTable).where(
                AgentTable.team_id == "system",
                AgentTable.archived_at.is_(None),
            )
        )
    ).all()

    # Batch get agent data
    agent_ids = [agent.id for agent in agents]
    agent_data_list = await db.scalars(
        select(AgentDataTable).where(AgentDataTable.id.in_(agent_ids))
    )
    agent_data_map = {data.id: data for data in agent_data_list}

    # Render agents concurrently
    rendered_agents_tasks = []
    for agent in agents:
        agent_model = Agent.model_validate(agent)
        rendered_agents_tasks.append(render_agent(agent_model))

    rendered_agents = await asyncio.gather(*rendered_agents_tasks)

    # Convert to AgentResponse objects
    response_tasks = []
    for agent in rendered_agents:
        agent_data = (
            AgentData.model_validate(agent_data_map.get(agent.id))
            if agent.id in agent_data_map
            else None
        )
        response_tasks.append(AgentResponse.from_agent(agent, agent_data))

    return await asyncio.gather(*response_tasks)


@agent_router.get(
    "/agents/{agent_id}",
    tags=["Agent"],
    operation_id="get_agent",
)
async def get_agent(
    agent_id: str = Path(..., description="ID or slug of the agent to retrieve"),
) -> Response:
    """Get a single agent by ID or slug.

    **Path Parameters:**
    * `agent_id` - ID or slug of the agent to retrieve

    **Returns:**
    * `AgentResponse` - Agent configuration with additional processed data

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await get_agent_by_id_or_slug(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

    # Get agent data
    agent_data = await AgentData.get(agent.id)

    agent_response = await AgentResponse.from_agent(agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@agent_router.get(
    "/agents/{agent_id}/editable",
    tags=["Agent"],
    operation_id="get_agent_editable",
)
async def get_agent_editable(
    agent_id: str = Path(..., description="ID or slug of the agent to retrieve"),
) -> Response:
    """Get a single agent by ID or slug with full editable fields.

    **Path Parameters:**
    * `agent_id` - ID or slug of the agent to retrieve

    **Returns:**
    * `AgentUpdate` - Full agent configuration for editing

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await get_agent_by_id_or_slug(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

    editable_agent = AgentUpdate.model_validate(agent)
    return Response(
        content=editable_agent.model_dump_json(),
        media_type="application/json",
    )


@agent_router.get(
    "/agents/{agent_id}/export",
    tags=["Agent"],
    operation_id="export_agent",
)
async def export_agent(
    agent_id: str = Path(..., description="ID of the agent to export"),
) -> Response:
    """Export agent configuration as YAML.

    **Path Parameters:**
    * `agent_id` - ID of the agent to export

    **Returns:**
    * `str` - YAML configuration of the agent

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )
    yaml_content = agent.to_yaml()
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{agent_id}.yaml"'},
    )


@agent_router.put(
    "/agents/{agent_id}/import",
    tags=["Agent"],
    operation_id="import_agent",
    response_class=PlainTextResponse,
)
async def import_agent(
    agent_id: str = Path(...),
    file: UploadFile = File(
        ..., description="YAML file containing agent configuration"
    ),
) -> str:
    """Import agent configuration from YAML file.
    Only updates existing agents, will not create new ones.

    **Path Parameters:**
    * `agent_id` - ID of the agent to update

    **Request Body:**
    * `file` - YAML file containing agent configuration

    **Returns:**
    * `str` - Success message

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid YAML or agent configuration
        - 404: Agent not found
        - 500: Server error
    """
    # Read and parse YAML
    content = await file.read()
    try:
        yaml_data = safe_load(content)
    except Exception as e:
        raise IntentKitAPIError(
            status_code=400, key="BadRequest", message=f"Invalid YAML format: {e}"
        )

    # Create Agent instance from YAML
    try:
        agent = AgentUpdate.model_validate(yaml_data)
    except ValidationError as e:
        raise IntentKitAPIError(400, "BadRequest", f"Invalid agent configuration: {e}")

    # Update-only: override_agent 404s when the agent doesn't exist
    # (override semantics: unspecified fields reset).
    _ = await override_agent(agent_id, agent, "admin")

    return "Agent import successful"


@agent_router.post(
    "/agents/upload-picture",
    tags=["Agent"],
    status_code=200,
    operation_id="upload_agent_picture",
    summary="Upload Agent Picture",
)
async def upload_agent_picture(
    file: UploadFile = File(..., description="Image file to upload as agent picture"),
) -> dict[str, str]:
    """Upload an image to S3 for use as an agent picture.

    Accepts image files (JPEG, PNG, GIF, WebP). Max size 5MB.

    **Returns:**
    * `dict` with `path` - The relative S3 path of the uploaded image
    """
    path = await validate_and_store_image(file, "avatars/")
    return {"path": path}


@agent_router.put(
    "/agents/{agent_id}/archive",
    tags=["Agent"],
    status_code=204,
    operation_id="archive_agent",
    summary="Archive Agent",
)
async def archive_agent(
    agent_id: str = Path(..., description="ID of the agent to archive"),
) -> Response:
    """Archive an agent by setting archived_at timestamp.

    **Path Parameters:**
    * `agent_id` - ID of the agent to archive

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
        - 500: Database error
    """
    # Check if agent exists
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    # A sub-agent of a public agent cannot be archived while referenced.
    await ensure_not_referenced_by_public_agent(agent.id, agent.slug)

    # Update archived_at in database
    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent_id))
        agent_row = result.scalar_one_or_none()
        if not agent_row:
            raise IntentKitAPIError(404, "NotFound", "Agent not found")

        agent_row.archived_at = datetime.now(UTC)
        await db.commit()

    invalidate_lead_cache(agent.team_id or "system")
    return Response(status_code=204)


@agent_router.put(
    "/agents/{agent_id}/reactivate",
    tags=["Agent"],
    status_code=204,
    operation_id="reactivate_agent",
    summary="Reactivate Agent",
)
async def reactivate_agent(
    agent_id: str = Path(..., description="ID of the agent to reactivate"),
) -> Response:
    """Reactivate an archived agent by clearing archived_at timestamp.

    **Path Parameters:**
    * `agent_id` - ID of the agent to reactivate

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
        - 500: Database error
    """
    # Check if agent exists
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    # Un-archiving a public agent revives its guest-facing call_agent
    # surface: its sub-agents must all (still) be public.
    if is_public_visibility(agent.visibility):
        await ensure_sub_agents_public(
            agent.sub_agents,
            exclude={ref for ref in (agent.id, agent.slug) if ref},
        )

    # Clear archived_at in database
    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent_id))
        agent_row = result.scalar_one_or_none()
        if not agent_row:
            raise IntentKitAPIError(404, "NotFound", "Agent not found")

        agent_row.archived_at = None
        await db.commit()

    invalidate_lead_cache(agent.team_id or "system")
    return Response(status_code=204)
