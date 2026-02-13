import asyncio
import importlib
import logging
from datetime import UTC, datetime
from typing import TypedDict

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Path,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from yaml import safe_load

from intentkit.clients.twitter import unlink_twitter
from intentkit.config.db import get_db, get_session
from intentkit.core.agent import (
    create_agent,
    deploy_agent,
    override_agent,
    patch_agent,
)
from intentkit.core.agent import (
    get_agent as get_agent_by_id,
)
from intentkit.core.avatar import generate_avatar
from intentkit.core.engine import clean_agent_memory
from intentkit.core.template import render_agent
from intentkit.models.agent import (
    Agent,
    AgentCreate,
    AgentResponse,
    AgentTable,
    AgentUpdate,
)
from intentkit.models.agent_data import AgentData, AgentDataTable
from intentkit.skills import __all__ as skill_categories
from intentkit.utils.error import IntentKitAPIError

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

    if not new_agent.picture:
        try:
            generated_avatar = await generate_avatar(new_agent.id, new_agent)
            if generated_avatar:
                new_agent.picture = generated_avatar
        except Exception as e:
            logger.error(f"Failed to auto-generate avatar: {e}")
    latest_agent, agent_data = await create_agent(new_agent)

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
    if not agent.picture:
        try:
            generated_avatar = await generate_avatar(agent_id, agent)
            if generated_avatar:
                agent.picture = generated_avatar
        except Exception as e:
            logger.error(f"Failed to auto-generate avatar: {e}")

    latest_agent, agent_data = await override_agent(agent_id, agent)

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
    # Check if we should auto-generate an avatar
    # Only generate if picture is not being explicitly set AND the existing agent has no picture
    update_fields = agent.model_dump(exclude_unset=True)
    if "picture" not in update_fields:
        existing_agent = await get_agent_by_id(agent_id)
        if existing_agent and not existing_agent.picture:
            try:
                generated_avatar = await generate_avatar(agent_id, agent)
                if generated_avatar:
                    agent.picture = generated_avatar
            except Exception as e:
                logger.error(f"Failed to auto-generate avatar: {e}")

    latest_agent, agent_data = await patch_agent(agent_id, agent)

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
        await db.scalars(select(AgentTable).where(AgentTable.archived_at.is_(None)))
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
    agent_id: str = Path(..., description="ID of the agent to retrieve"),
) -> Response:
    """Get a single agent by ID.

    **Path Parameters:**
    * `agent_id` - ID of the agent to retrieve

    **Returns:**
    * `AgentResponse` - Agent configuration with additional processed data

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

    # Get agent data
    agent_data = await AgentData.get(agent_id)

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
    agent_id: str = Path(..., description="ID of the agent to retrieve"),
) -> Response:
    """Get a single agent by ID with full editable fields.

    **Path Parameters:**
    * `agent_id` - ID of the agent to retrieve

    **Returns:**
    * `AgentUpdate` - Full agent configuration for editing

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

    editable_agent = AgentUpdate.model_validate(agent)
    return Response(
        content=editable_agent.model_dump_json(),
        media_type="application/json",
    )


class MemCleanRequest(BaseModel):
    """Request model for agent memory cleanup endpoint.

    Attributes:
        agent_id (str): Agent ID to clean
        chat_id (str): Chat ID to clean
        clean_skills_memory (bool): To clean the skills data.
        clean_agent_memory (bool): To clean the agent memory.
    """

    agent_id: str
    clean_agent_memory: bool
    clean_skills_memory: bool
    chat_id: str | None = Field("")


@agent_router.post(
    "/agent/clean-memory",
    tags=["Agent"],
    status_code=204,
    operation_id="clean_agent_memory",
)
async def clean_memory(
    request: MemCleanRequest = Body(
        MemCleanRequest, description="Agent memory cleanup request"
    ),
):
    """Clear an agent memory.

    **Request Body:**
    * `request` - The execution request containing agent ID, message, and thread ID

    **Returns:**
    * `str` - Formatted response lines from agent memory cleanup

    **Raises:**
    * `IntentKitAPIError`:
        - 400: If input parameters are invalid (empty agent_id, thread_id, or message text)
        - 404: If agent not found
        - 500: For other server-side errors
    """
    # Validate input parameters
    if not request.agent_id or not request.agent_id.strip():
        raise IntentKitAPIError(
            status_code=400, key="BadRequest", message="Agent ID cannot be empty"
        )

    try:
        agent = await get_agent_by_id(request.agent_id)
        if not agent:
            raise IntentKitAPIError(
                status_code=404,
                key="NotFound",
                message=f"Agent with id {request.agent_id} not found",
            )

        _ = await clean_agent_memory(
            request.agent_id,
            request.chat_id or "",
            clean_agent=request.clean_agent_memory,
            clean_skill=request.clean_skills_memory,
        )
    except NoResultFound:
        raise IntentKitAPIError(
            status_code=404,
            key="NotFound",
            message=f"Agent {request.agent_id} not found",
        )
    except SQLAlchemyError as e:
        raise IntentKitAPIError(
            status_code=500,
            key="InternalServerError",
            message=f"Database error: {str(e)}",
        )
    except ValueError as e:
        raise IntentKitAPIError(status_code=400, key="BadRequest", message=str(e))
    except Exception as e:
        raise IntentKitAPIError(
            status_code=500,
            key="InternalServerError",
            message=f"Server error: {str(e)}",
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
    # Ensure agent.skills is initialized
    if agent.skills is None:
        agent.skills = {}

    # fill all skill categories
    for category in skill_categories:
        try:
            # Dynamically import the skill module
            skill_module = importlib.import_module(f"intentkit.skills.{category}")

            # Check if the module has a Config class and get_skills function
            if hasattr(skill_module, "Config") and hasattr(skill_module, "get_skills"):
                # Get or create the config for this category
                category_config = agent.skills.get(category, {})

                # Ensure 'enabled' field exists (required by SkillConfig)
                if "enabled" not in category_config:
                    category_config["enabled"] = False

                # Ensure states dict exists
                if "states" not in category_config:
                    category_config["states"] = {}

                # Get all available skill states from the module
                available_skills = []
                if hasattr(skill_module, "SkillStates") and hasattr(
                    skill_module.SkillStates, "__annotations__"
                ):
                    available_skills = list(
                        skill_module.SkillStates.__annotations__.keys()
                    )
                # Add missing skills with disabled state
                for skill_name in available_skills:
                    if skill_name not in category_config["states"]:
                        category_config["states"][skill_name] = "disabled"

                # Get all required fields from Config class and its base classes
                config_class = skill_module.Config
                # Get all base classes of Config
                all_bases = [config_class]
                for base in config_class.__mro__[1:]:
                    if base is TypedDict or base is dict or base is object:
                        continue
                    all_bases.append(base)

                # Collect all required fields from Config and its base classes
                for base in all_bases:
                    if hasattr(base, "__annotations__"):
                        for field_name, field_type in base.__annotations__.items():
                            # Skip fields already set or marked as NotRequired
                            if field_name in category_config or "NotRequired" in str(
                                field_type
                            ):
                                continue
                            # Add default value based on type
                            if field_name != "states":  # states already handled above
                                if "str" in str(field_type):
                                    category_config[field_name] = ""
                                elif "bool" in str(field_type):
                                    category_config[field_name] = False
                                elif "int" in str(field_type):
                                    category_config[field_name] = 0
                                elif "float" in str(field_type):
                                    category_config[field_name] = 0.0
                                elif "list" in str(field_type) or "List" in str(
                                    field_type
                                ):
                                    category_config[field_name] = []
                                elif "dict" in str(field_type) or "Dict" in str(
                                    field_type
                                ):
                                    category_config[field_name] = {}

                # Update the agent's skills config
                agent.skills[category] = category_config
        except (ImportError, AttributeError):
            # Skip if module import fails or doesn't have required components
            pass
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
    # First check if agent exists
    existing_agent = await get_agent_by_id(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

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

    # Get the latest agent from create_or_update
    _ = await deploy_agent(agent_id, agent, "admin")

    return "Agent import successful"


@agent_router.put(
    "/agents/{agent_id}/twitter/unlink",
    tags=["OAuth"],
    operation_id="unlink_twitter",
    response_class=Response,
)
async def unlink_twitter_endpoint(
    agent_id: str = Path(..., description="ID of the agent to unlink from X"),
) -> Response:
    """Unlink X from an agent.

    **Path Parameters:**
    * `agent_id` - ID of the agent to unlink from X

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    # Check if agent exists
    agent = await get_agent_by_id(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "NotFound", "Agent not found")

    # Call the unlink_twitter function from clients.twitter
    agent_data = await unlink_twitter(agent_id)

    agent_response = await AgentResponse.from_agent(agent, agent_data)

    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


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

    # Update archived_at in database
    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent_id))
        agent_row = result.scalar_one_or_none()
        if not agent_row:
            raise IntentKitAPIError(404, "NotFound", "Agent not found")

        agent_row.archived_at = datetime.now(UTC)
        await db.commit()

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

    # Clear archived_at in database
    async with get_session() as db:
        result = await db.execute(select(AgentTable).where(AgentTable.id == agent_id))
        agent_row = result.scalar_one_or_none()
        if not agent_row:
            raise IntentKitAPIError(404, "NotFound", "Agent not found")

        agent_row.archived_at = None
        await db.commit()

    return Response(status_code=204)
