import importlib
import json
import logging
from typing import Annotated, Optional, TypedDict

from aiogram import Bot
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError
from cdp import Wallet
from cdp.cdp import Cdp
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
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

from app.config.config import config
from app.core.engine import clean_agent_memory
from clients.twitter import unlink_twitter
from models.agent import (
    Agent,
    AgentCreate,
    AgentData,
    AgentDataTable,
    AgentResponse,
    AgentTable,
    AgentUpdate,
)
from models.db import get_db
from models.user import User
from skills import __all__ as skill_categories
from utils.middleware import create_jwt_middleware
from utils.slack_alert import send_slack_message

admin_router_readonly = APIRouter()
admin_router = APIRouter()

# Create JWT middleware with admin config
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)

logger = logging.getLogger(__name__)


async def _process_agent(
    agent: AgentCreate, subject: str | None = None, slack_message: str | None = None
) -> tuple[Agent, AgentData]:
    """Shared function to process agent creation or update.

    Args:
        agent: Agent configuration to process
        subject: Optional subject from JWT token
        slack_message: Optional custom message for Slack notification

    Returns:
        tuple[Agent, AgentData]: Tuple of (processed agent, agent data)
    """
    logger.info(f"Processing agent: {agent}")
    if subject:
        agent.owner = subject

    # Get the latest agent from create_or_update
    latest_agent, is_new = await agent.create_or_update()

    # Process common post-creation/update steps
    agent_data = await _process_agent_post_actions(latest_agent, is_new, slack_message)

    return latest_agent, agent_data


async def _process_agent_post_actions(
    agent: Agent, is_new: bool = True, slack_message: str | None = None
) -> AgentData:
    """Process common actions after agent creation or update.

    Args:
        agent: The agent that was created or updated
        is_new: Whether the agent is newly created
        slack_message: Optional custom message for Slack notification

    Returns:
        AgentData: The processed agent data
    """
    has_wallet = False
    agent_data = None

    if not is_new:
        # Get agent data
        agent_data = await AgentData.get(agent.id)
        if agent_data and agent_data.cdp_wallet_data:
            has_wallet = True
            wallet_data = json.loads(agent_data.cdp_wallet_data)
        # Run clean_agent_memory in background
        # asyncio.create_task(clean_agent_memory(agent.id, clean_agent=True))

    if (
        not has_wallet
        and agent.skills
        and agent.skills.get("cdp")
        and agent.skills["cdp"].get("enabled")
    ):
        # create the wallet
        Cdp.configure(
            api_key_name=config.cdp_api_key_name,
            private_key=config.cdp_api_key_private_key.replace("\\n", "\n"),
        )
        network_id = agent.network_id or agent.cdp_network_id
        wallet = Wallet.create(network_id=network_id)
        wallet_data = wallet.export_data().to_dict()
        wallet_data["default_address_id"] = wallet.default_address.address_id
        if not agent_data:
            agent_data = AgentData(id=agent.id, cdp_wallet_data=json.dumps(wallet_data))
        else:
            agent_data.cdp_wallet_data = json.dumps(wallet_data)
        await agent_data.save()
        logger.info(
            "Wallet created for agent %s: %s",
            agent.id,
            wallet_data["default_address_id"],
        )

    # Send Slack notification
    slack_message = slack_message or ("Agent Created" if is_new else "Agent Updated")
    try:
        _send_agent_notification(agent, agent_data, wallet_data, slack_message)
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    return agent_data


async def _process_telegram_config(
    agent: AgentUpdate, existing_agent: Optional[Agent], agent_data: AgentData
) -> AgentData:
    """Process telegram configuration for an agent.

    Args:
        agent: The agent with telegram configuration
        agent_data: The agent data to update

    Returns:
        AgentData: The updated agent data
    """
    changes = agent.model_dump(exclude_unset=True)
    if not changes.get("telegram_entrypoint_enabled"):
        return agent_data

    if not changes.get("telegram_config") or not changes.get("telegram_config").get(
        "token"
    ):
        return agent_data

    tg_bot_token = changes.get("telegram_config").get("token")

    if existing_agent and existing_agent.telegram_config.get("token") == tg_bot_token:
        return agent_data

    try:
        bot = Bot(token=tg_bot_token)
        bot_info = await bot.get_me()
        agent_data.telegram_id = str(bot_info.id)
        agent_data.telegram_username = bot_info.username
        agent_data.telegram_name = bot_info.first_name
        if bot_info.last_name:
            agent_data.telegram_name = f"{bot_info.first_name} {bot_info.last_name}"
        await agent_data.save()
        try:
            await bot.close()
        except Exception:
            pass
        return agent_data
    except (
        TelegramUnauthorizedError,
        TelegramConflictError,
        TokenValidationError,
    ) as req_err:
        logger.error(
            f"Unauthorized err getting telegram bot username with token {tg_bot_token}: {req_err}",
        )
        return agent_data
    except Exception as e:
        logger.error(
            f"Error getting telegram bot username with token {tg_bot_token}: {e}",
        )
        return agent_data


def _send_agent_notification(
    agent: Agent, agent_data: AgentData, wallet_data: dict, message: str
) -> None:
    """Send a notification about agent creation or update.

    Args:
        agent: The agent that was created or updated
        agent_data: The agent data to update
        wallet_data: The agent's wallet data
        message: The notification message
    """
    # Format autonomous configurations - show only enabled ones with their id, name, and schedule
    autonomous_formatted = ""
    if agent.autonomous:
        enabled_autonomous = [auto for auto in agent.autonomous if auto.enabled]
        if enabled_autonomous:
            autonomous_items = []
            for auto in enabled_autonomous:
                schedule = (
                    f"cron: {auto.cron}" if auto.cron else f"minutes: {auto.minutes}"
                )
                autonomous_items.append(
                    f"• {auto.id}: {auto.name or 'Unnamed'} ({schedule})"
                )
            autonomous_formatted = "\n".join(autonomous_items)
        else:
            autonomous_formatted = "No enabled autonomous configurations"
    else:
        autonomous_formatted = "None"

    # Format skills - find categories with enabled: true and list skills in public/private states
    skills_formatted = ""
    if agent.skills:
        enabled_categories = []
        for category, skill_config in agent.skills.items():
            if skill_config and skill_config.get("enabled") is True:
                skills_list = []
                states = skill_config.get("states", {})
                public_skills = [
                    skill for skill, state in states.items() if state == "public"
                ]
                private_skills = [
                    skill for skill, state in states.items() if state == "private"
                ]

                if public_skills:
                    skills_list.append(f"  Public: {', '.join(public_skills)}")
                if private_skills:
                    skills_list.append(f"  Private: {', '.join(private_skills)}")

                if skills_list:
                    enabled_categories.append(
                        f"• {category}:\n{chr(10).join(skills_list)}"
                    )

        if enabled_categories:
            skills_formatted = "\n".join(enabled_categories)
        else:
            skills_formatted = "No enabled skills"
    else:
        skills_formatted = "None"

    send_slack_message(
        message,
        attachments=[
            {
                "color": "good",
                "fields": [
                    {"title": "ENV", "short": True, "value": config.env},
                    {"title": "Number", "short": True, "value": agent.number},
                    {"title": "ID", "short": True, "value": agent.id},
                    {"title": "Name", "short": True, "value": agent.name},
                    {"title": "Model", "short": True, "value": agent.model},
                    {
                        "title": "GOAT Enabled",
                        "short": True,
                        "value": str(agent.goat_enabled),
                    },
                    {
                        "title": "X Username",
                        "short": True,
                        "value": agent_data.twitter_username,
                    },
                    {
                        "title": "Telegram Enabled",
                        "short": True,
                        "value": str(agent.telegram_entrypoint_enabled),
                    },
                    {
                        "title": "Telegram Username",
                        "short": True,
                        "value": agent_data.telegram_username,
                    },
                    {
                        "title": "Wallet Provider",
                        "short": True,
                        "value": agent.wallet_provider,
                    },
                    {
                        "title": "Network",
                        "short": True,
                        "value": agent.network_id or agent.cdp_network_id or "Default",
                    },
                    {
                        "title": "Wallet Address",
                        "value": wallet_data.get("default_address_id"),
                    },
                    {
                        "title": "Autonomous",
                        "value": autonomous_formatted,
                    },
                    {
                        "title": "Skills",
                        "value": skills_formatted,
                    },
                ],
            }
        ],
    )


@admin_router.post(
    "/agents",
    tags=["Agent"],
    status_code=201,
    operation_id="post_agent_deprecated",
    deprecated=True,
)
async def create_or_update_agent(
    agent: AgentCreate = Body(AgentCreate, description="Agent configuration"),
    subject: str = Depends(verify_jwt),
) -> Response:
    """Create or update an agent.

    THIS ENDPOINT IS DEPRECATED. Please use POST /agents/v2 for creating new agents.

    This endpoint:
    1. Validates agent ID format
    2. Creates or updates agent configuration
    3. Reinitializes agent if already in cache
    4. Masks sensitive data in response

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `AgentResponse` - Updated agent configuration with additional processed data

    **Raises:**
    * `HTTPException`:
        - 400: Invalid agent ID format
        - 500: Database error
    """
    latest_agent, agent_data = await _process_agent(agent, subject)
    agent_response = AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router_readonly.post(
    "/agent/validate",
    tags=["Agent"],
    status_code=204,
    operation_id="validate_agent_create",
)
async def validate_agent_create(
    user_id: Annotated[
        Optional[str], Query(description="Optional user ID for authorization check")
    ] = None,
    input: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
) -> Response:
    """Validate agent configuration.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `204 No Content` - Agent configuration is valid

    **Raises:**
    * `HTTPException`:
        - 400: Invalid agent configuration
        - 422: Invalid agent configuration from intentkit core
        - 500: Server error
    """
    if not input.owner:
        raise HTTPException(status_code=400, detail="Owner is required")
    max_fee = 100
    if user_id:
        if input.owner != user_id:
            raise HTTPException(status_code=400, detail="Owner does not match user ID")
        user = await User.get(user_id)
        if user:
            max_fee += user.nft_count * 10
    if input.fee_percentage and input.fee_percentage > max_fee:
        raise HTTPException(status_code=400, detail="Fee percentage too high")
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
        Optional[str], Query(description="Optional user ID for authorization check")
    ] = None,
    input: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
) -> Response:
    """Validate agent configuration.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `204 No Content` - Agent configuration is valid

    **Raises:**
    * `HTTPException`:
        - 400: Invalid agent configuration
        - 422: Invalid agent configuration from intentkit core
        - 500: Server error
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    max_fee = 100
    if user_id:
        if agent.owner != user_id:
            raise HTTPException(status_code=400, detail="Owner does not match user ID")
        user = await User.get(user_id)
        if user:
            max_fee += user.nft_count * 10
    if input.fee_percentage and input.fee_percentage > max_fee:
        raise HTTPException(status_code=400, detail="Fee percentage too high")
    input.validate_autonomous_schedule()
    return Response(status_code=204)


@admin_router.post(
    "/agents/v2",
    tags=["Agent"],
    operation_id="create_agent",
    summary="Create Agent",
    response_model=AgentResponse,
    responses={
        200: {"model": AgentResponse, "description": "Agent already exists"},
        201: {"model": AgentResponse, "description": "Agent created"},
        400: {"description": "Other client errors except format error"},
        422: {"description": "Invalid agent configuration"},
        500: {"description": "Server error"},
    },
)
async def create_agent(
    input: AgentUpdate = Body(AgentUpdate, description="Agent configuration"),
    subject: str = Depends(verify_jwt),
) -> Response:
    """Create a new agent.

    **Request Body:**
    * `agent` - Agent configuration

    **Returns:**
    * `AgentResponse` - Created agent configuration with additional processed data

    **Raises:**
    * `HTTPException`:
        - 400: Invalid agent ID format or agent ID already exists
        - 500: Database error
    """
    agent = AgentCreate.model_validate(input)
    if subject:
        agent.owner = subject

    # Check for existing agent by upstream_id
    existing = await agent.get_by_upstream_id()
    if existing:
        agent_data = await AgentData.get(existing.id)
        agent_response = AgentResponse.from_agent(existing, agent_data)
        return Response(
            status_code=200,
            content=agent_response.model_dump_json(),
            media_type="application/json",
            headers={"ETag": agent_response.etag()},
        )
    # Create new agent
    latest_agent = await agent.create()
    # Process common post-creation actions
    agent_data = await _process_agent_post_actions(latest_agent, True, "Agent Created")
    agent_data = await _process_telegram_config(input, None, agent_data)
    agent_response = AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        status_code=201,
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router.patch(
    "/agents/{agent_id}", tags=["Agent"], status_code=200, operation_id="update_agent"
)
async def update_agent(
    agent_id: str = Path(..., description="ID of the agent to update"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent update configuration"),
    subject: str = Depends(verify_jwt),
) -> Response:
    """Update an existing agent.

    Use input to update agent configuration. If some fields are not provided, they will not be changed.

    **Path Parameters:**
    * `agent_id` - ID of the agent to update

    **Request Body:**
    * `agent` - Agent update configuration

    **Returns:**
    * `AgentResponse` - Updated agent configuration with additional processed data

    **Raises:**
    * `HTTPException`:
        - 400: Invalid agent ID format
        - 404: Agent not found
        - 403: Permission denied (if owner mismatch)
        - 500: Database error
    """
    if subject:
        agent.owner = subject

    existing_agent = await Agent.get(agent_id)
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update agent
    latest_agent = await agent.update(agent_id)

    # Process common post-update actions
    agent_data = await _process_agent_post_actions(latest_agent, False, "Agent Updated")

    agent_data = await _process_telegram_config(agent, existing_agent, agent_data)

    agent_response = AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router.put(
    "/agents/{agent_id}", tags=["Agent"], status_code=200, operation_id="override_agent"
)
async def override_agent(
    agent_id: str = Path(..., description="ID of the agent to update"),
    agent: AgentUpdate = Body(AgentUpdate, description="Agent update configuration"),
    subject: str = Depends(verify_jwt),
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
    * `HTTPException`:
        - 400: Invalid agent ID format
        - 404: Agent not found
        - 403: Permission denied (if owner mismatch)
        - 500: Database error
    """
    if subject:
        agent.owner = subject

    if not agent.owner:
        raise HTTPException(status_code=400, detail="Owner is required")

    existing_agent = await Agent.get(agent_id)
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update agent
    latest_agent = await agent.override(agent_id)

    # Process common post-update actions
    agent_data = await _process_agent_post_actions(
        latest_agent, False, "Agent Overridden"
    )

    agent_data = await _process_telegram_config(agent, existing_agent, agent_data)

    agent_response = AgentResponse.from_agent(latest_agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


@admin_router_readonly.get(
    "/agents",
    tags=["Agent"],
    dependencies=[Depends(verify_jwt)],
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
        AgentResponse.from_agent(
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
    dependencies=[Depends(verify_jwt)],
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
    * `HTTPException`:
        - 404: Agent not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get agent data
    agent_data = await AgentData.get(agent_id)

    agent_response = AgentResponse.from_agent(agent, agent_data)

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
    dependencies=[Depends(verify_jwt)],
    operation_id="clean_agent_memory",
)
@admin_router.post(
    "/agents/clean-memory",
    tags=["Agent"],
    status_code=201,
    dependencies=[Depends(verify_jwt)],
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
    * `HTTPException`:
        - 400: If input parameters are invalid (empty agent_id, thread_id, or message text)
        - 404: If agent not found
        - 500: For other server-side errors
    """
    # Validate input parameters
    if not request.agent_id or not request.agent_id.strip():
        raise HTTPException(status_code=400, detail="Agent ID cannot be empty")

    try:
        agent = await Agent.get(request.agent_id)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with id {request.agent_id} not found",
            )

        await clean_agent_memory(
            request.agent_id,
            request.chat_id,
            clean_agent=request.clean_agent_memory,
            clean_skill=request.clean_skills_memory,
        )
    except NoResultFound:
        raise HTTPException(
            status_code=404, detail=f"Agent {request.agent_id} not found"
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@admin_router_readonly.get(
    "/agents/{agent_id}/export",
    tags=["Agent"],
    operation_id="export_agent",
    dependencies=[Depends(verify_jwt)],
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
    * `HTTPException`:
        - 404: Agent not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Ensure agent.skills is initialized
    if agent.skills is None:
        agent.skills = {}

    # Process all skill categories
    for category in skill_categories:
        try:
            # Dynamically import the skill module
            skill_module = importlib.import_module(f"skills.{category}")

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
    subject: str = Depends(verify_jwt),
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
    * `HTTPException`:
        - 400: Invalid YAML or agent configuration
        - 404: Agent not found
        - 500: Server error
    """
    # First check if agent exists
    existing_agent = await Agent.get(agent_id)
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Read and parse YAML
    content = await file.read()
    try:
        yaml_data = safe_load(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {e}")

    # Create Agent instance from YAML
    try:
        agent = AgentUpdate.model_validate(yaml_data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid agent configuration: {e}")

    # Get the latest agent from create_or_update
    latest_agent = await agent.update(agent_id)

    # Process common post-creation/update steps
    agent_data = await _process_agent_post_actions(
        latest_agent, False, "Agent Updated via YAML Import"
    )

    await _process_telegram_config(agent, existing_agent, agent_data)

    return "Agent import successful"


@admin_router.put(
    "/agents/{agent_id}/twitter/unlink",
    tags=["Agent"],
    operation_id="unlink_twitter",
    dependencies=[Depends(verify_jwt)],
    response_class=Response,
)
async def unlink_twitter_endpoint(
    agent_id: str = Path(..., description="ID of the agent to unlink from X"),
) -> Response:
    """Unlink X from an agent.

    **Path Parameters:**
    * `agent_id` - ID of the agent to unlink from X

    **Raises:**
    * `HTTPException`:
        - 404: Agent not found
    """
    # Check if agent exists
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Call the unlink_twitter function from clients.twitter
    agent_data = await unlink_twitter(agent_id)

    agent_response = AgentResponse.from_agent(agent, agent_data)

    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )
