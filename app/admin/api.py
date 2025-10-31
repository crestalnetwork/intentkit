import importlib
import logging
from typing import Annotated, TypedDict

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Path,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import NoResultFound
from yaml import safe_load

from intentkit.clients.twitter import unlink_twitter
from intentkit.core.agent import (
    create_agent,
    deploy_agent,
    override_agent,
    process_agent_wallet,
    send_agent_notification,
)
from intentkit.core.engine import clean_agent_memory
from intentkit.models.agent import (
    Agent,
    AgentCreate,
    AgentResponse,
    AgentTable,
    AgentUpdate,
)
from intentkit.models.agent_data import AgentData, AgentDataTable
from intentkit.models.db import get_db
from intentkit.skills import __all__ as skill_categories
from intentkit.utils.error import IntentKitAPIError

from app.auth import verify_admin_jwt

admin_router_readonly = APIRouter()
admin_router = APIRouter()

logger = logging.getLogger(__name__)


@admin_router_readonly.post(
    "/agent/validate",
    tags=["Agent"],
    status_code=204,
    operation_id="validate_agent_create",
)
async def validate_agent_create(
    user_id: Annotated[
        str | None, Query(description="Optional user ID for authorization check")
    ] = None,
    input: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
) -> Response:
    """Validate agent configuration.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `204 No Content` - Agent configuration is valid

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid agent configuration
        - 422: Invalid agent configuration from intentkit core
        - 500: Server error
    """
    # if not input.owner:
    #     raise IntentKitAPIError(
    #         status_code=400, key="BadRequest", message="Owner is required"
    #     )
    # max_fee = 100
    # if user_id:
    #     if input.owner != user_id:
    #         raise IntentKitAPIError(
    #             status_code=400,
    #             key="BadRequest",
    #             message="Owner does not match user ID",
    #         )
    # user = await User.get(user_id)
    # if user:
    #     max_fee += user.nft_count * 10
    # if input.fee_percentage and input.fee_percentage > max_fee:
    #     raise IntentKitAPIError(
    #         status_code=400, key="BadRequest", message="Fee percentage too high"
    #     )
    input.validate_autonomous_schedule()
    return Response(status_code=204)


@admin_router_readonly.post(
    "/agents/{agent_id}/validate",
    tags=["Agent"],
    status_code=204,
    operation_id="validate_agent_update",
)
async def validate_agent_update(
    agent_id: Annotated[str, Path(description="Agent ID")],
    user_id: Annotated[
        str | None, Query(description="Optional user ID for authorization check")
    ] = None,
    input: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
) -> Response:
    """Validate agent configuration.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `204 No Content` - Agent configuration is valid

    **Raises:**
    * `IntentKitAPIError`:
        - 400: Invalid agent configuration
        - 422: Invalid agent configuration from intentkit core
        - 500: Server error
    """
    # if not input.owner:
    #     raise IntentKitAPIError(
    #         status_code=400, key="BadRequest", message="Owner is required"
    #     )
    # max_fee = 100
    # if user_id:
    #     if input.owner != user_id:
    #         raise IntentKitAPIError(
    #             status_code=400,
    #             key="BadRequest",
    #             message="Owner does not match user ID",
    #         )
    #     user = await User.get(user_id)
    #     if user:
    #         max_fee += user.nft_count * 10
    # if input.fee_percentage and input.fee_percentage > max_fee:
    #     raise IntentKitAPIError(
    #         status_code=400, key="BadRequest", message="Fee percentage too high"
    #     )
    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )
    # max_fee = 100
    if user_id:
        if agent.owner != user_id:
            raise IntentKitAPIError(
                status_code=400,
                key="BadRequest",
                message="Owner does not match user ID",
            )
        # user = await User.get(user_id)
        #     if user:
        #         max_fee += user.nft_count * 10
        # if input.fee_percentage and input.fee_percentage > max_fee:
        # raise IntentKitAPIError(
        #     status_code=400, key="BadRequest", message="Fee percentage too high"
        # )
    input.validate_autonomous_schedule()
    return Response(status_code=204)


@admin_router.post(
    "/agents/v2",
    tags=["Agent"],
    status_code=201,
    operation_id="create_agent_deprecated",
    responses={
        201: {"description": "Agent created successfully"},
    },
    deprecated=True,
)
@admin_router.post(
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
    subject: str = Depends(verify_admin_jwt),
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
    new_agent.owner = subject
    latest_agent, agent_data = await create_agent(new_agent)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header and appropriate status code
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
        status_code=201,
    )


@admin_router.patch(
    "/agents/{agent_id}",
    tags=["Agent"],
    status_code=200,
    operation_id="update_agent",
    deprecated=True,
)
async def update_agent(
    agent_id: str = Path(..., description="ID of the agent to update"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent update configuration"),
    subject: str = Depends(verify_admin_jwt),
) -> Response:
    """
    Deprecated, use the put method instead, it will override the agent instead of updating it.

    Use input to update agent configuration. If some fields are not provided, they will not be changed.

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
        - 403: Permission denied (if owner mismatch)
        - 500: Database error
    """
    if subject:
        agent.owner = subject

    existing_agent = await Agent.get(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404, key="NotFound", message="Agent not found"
        )

    # Update agent
    latest_agent = await agent.update(agent_id)

    # Process agent wallet with old provider for validation
    agent_data = await process_agent_wallet(
        latest_agent, existing_agent.wallet_provider
    )

    # Send Slack notification
    slack_message = "Agent Updated"
    try:
        send_agent_notification(latest_agent, agent_data, slack_message)
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router.put(
    "/agents/{agent_id}",
    tags=["Agent"],
    status_code=200,
    operation_id="override_agent",
    summary="Override Agent",
)
async def override_agent_endpoint(
    agent_id: str = Path(..., description="ID of the agent to update"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent update configuration"),
    subject: str = Depends(verify_admin_jwt),
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
        - 403: Permission denied (if owner mismatch)
        - 500: Database error
    """
    latest_agent, agent_data = await override_agent(agent_id, agent, subject)

    agent_response = await AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router_readonly.get(
    "/agents",
    tags=["Agent"],
    dependencies=[Depends(verify_admin_jwt)],
    operation_id="get_agents",
)
async def get_agents(db: AsyncSession = Depends(get_db)) -> list[AgentResponse]:
    """Get all agents with their quota information.

    **Returns:**
    * `list[AgentResponse]` - List of agents with their quota information and additional processed data
    """
    # Query all agents first
    agents = (await db.scalars(select(AgentTable))).all()

    # Batch get agent data
    agent_ids = [agent.id for agent in agents]
    agent_data_list = await db.scalars(
        select(AgentDataTable).where(AgentDataTable.id.in_(agent_ids))
    )
    agent_data_map = {data.id: data for data in agent_data_list}

    # Convert to AgentResponse objects
    return [
        await AgentResponse.from_agent(
            Agent.model_validate(agent),
            AgentData.model_validate(agent_data_map.get(agent.id))
            if agent.id in agent_data_map
            else None,
        )
        for agent in agents
    ]


@admin_router_readonly.get(
    "/agents/{agent_id}",
    tags=["Agent"],
    dependencies=[Depends(verify_admin_jwt)],
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
    agent = await Agent.get(agent_id)
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


@admin_router.post(
    "/agent/clean-memory",
    tags=["Agent"],
    status_code=204,
    dependencies=[Depends(verify_admin_jwt)],
    operation_id="clean_agent_memory",
)
@admin_router.post(
    "/agents/clean-memory",
    tags=["Agent"],
    status_code=201,
    dependencies=[Depends(verify_admin_jwt)],
    operation_id="clean_agent_memory_deprecated",
    deprecated=True,
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
        agent = await Agent.get(request.agent_id)
        if not agent:
            raise IntentKitAPIError(
                status_code=404,
                key="NotFound",
                message=f"Agent with id {request.agent_id} not found",
            )

        await clean_agent_memory(
            request.agent_id,
            request.chat_id,
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


@admin_router_readonly.get(
    "/agents/{agent_id}/export",
    tags=["Agent"],
    operation_id="export_agent",
    dependencies=[Depends(verify_admin_jwt)],
)
async def export_agent(
    agent_id: str = Path(..., description="ID of the agent to export"),
) -> str:
    """Export agent configuration as YAML.

    **Path Parameters:**
    * `agent_id` - ID of the agent to export

    **Returns:**
    * `str` - YAML configuration of the agent

    **Raises:**
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent = await Agent.get(agent_id)
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
                            field_type_str = str(field_type)
                            # Skip fields already set or marked as NotRequired
                            if (
                                field_name in category_config
                                or "notrequired" in field_type_str.lower()
                            ):
                                continue
                            # Add default value based on type
                            if field_name != "states":  # states already handled above
                                field_type_lower = field_type_str.lower()
                                if "str" in field_type_lower:
                                    category_config[field_name] = ""
                                elif "bool" in field_type_lower:
                                    category_config[field_name] = False
                                elif "int" in field_type_lower:
                                    category_config[field_name] = 0
                                elif "float" in field_type_lower:
                                    category_config[field_name] = 0.0
                                elif "list" in field_type_lower:
                                    category_config[field_name] = []
                                elif "dict" in field_type_lower:
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


@admin_router.put(
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
    subject: str = Depends(verify_admin_jwt),
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
    existing_agent = await Agent.get(agent_id)
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
    latest_agent, agent_data = await deploy_agent(agent_id, agent, subject)

    return "Agent import successful"


@admin_router.put(
    "/agents/{agent_id}/twitter/unlink",
    tags=["Agent"],
    operation_id="unlink_twitter",
    dependencies=[Depends(verify_admin_jwt)],
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
    agent = await Agent.get(agent_id)
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
