import asyncio
import json
import logging

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
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from yaml import safe_load

from app.config.config import config
from app.core.engine import clean_agent_memory
from models.agent import Agent, AgentData, AgentResponse
from models.db import get_db
from utils.middleware import create_jwt_middleware
from utils.slack_alert import send_slack_message

admin_router_readonly = APIRouter()
admin_router = APIRouter()

# Create JWT middleware with admin config
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)

logger = logging.getLogger(__name__)


async def _process_agent(
    agent: Agent, subject: str | None = None, slack_message: str | None = None
) -> tuple[Agent, AgentData]:
    """Shared function to process agent creation or update.

    Args:
        agent: Agent configuration to process
        subject: Optional subject from JWT token
        slack_message: Optional custom message for Slack notification

    Returns:
        tuple[Agent, AgentData]: Tuple of (processed agent, agent data)
    """
    if subject:
        agent.owner = subject

    # Get the latest agent from create_or_update
    latest_agent, is_new = await agent.create_or_update()

    has_wallet = False
    agent_data = None
    if not is_new:
        agent_data = await AgentData.get(latest_agent.id)
        if agent_data and agent_data.cdp_wallet_data:
            has_wallet = True
            wallet_data = json.loads(agent_data.cdp_wallet_data)
        # Run clean_agent_memory in background
        asyncio.create_task(clean_agent_memory(latest_agent.id, clean_agent=True))

    if not has_wallet:
        # create the wallet
        Cdp.configure(
            api_key_name=config.cdp_api_key_name,
            private_key=config.cdp_api_key_private_key.replace("\\n", "\n"),
        )
        wallet = Wallet.create(network_id=latest_agent.cdp_network_id)
        wallet_data = wallet.export_data().to_dict()
        wallet_data["default_address_id"] = wallet.default_address.address_id
        if not agent_data:
            agent_data = AgentData(
                id=latest_agent.id, cdp_wallet_data=json.dumps(wallet_data)
            )
        else:
            agent_data.cdp_wallet_data = json.dumps(wallet_data)
        await agent_data.save()
        logger.info(
            "Wallet created for agent %s: %s",
            latest_agent.id,
            wallet_data["default_address_id"],
        )

    if agent.telegram_config:
        tg_bot_token = agent.telegram_config.get("token")
        if tg_bot_token:
            try:
                bot = Bot(token=tg_bot_token)
                bot_info = await bot.get_me()
                agent_data.telegram_id = str(bot_info.id)
                agent_data.telegram_username = bot_info.username
                agent_data.telegram_name = bot_info.first_name
                await agent_data.save()
                try:
                    await bot.close()
                except Exception:
                    pass
            except (
                TelegramUnauthorizedError,
                TelegramConflictError,
                TokenValidationError,
            ) as req_err:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unauthorized err getting telegram bot username with token {tg_bot_token}: {req_err}",
                )
            except Exception as e:
                raise Exception(
                    f"Error getting telegram bot username with token {tg_bot_token}: {e}"
                )

    # Send Slack notification
    slack_message = slack_message or ("Agent Created" if is_new else "Agent Updated")
    send_slack_message(
        slack_message,
        attachments=[
            {
                "color": "good",
                "fields": [
                    {"title": "ENV", "short": True, "value": config.env},
                    {"title": "Total", "short": True, "value": await Agent.count()},
                    {"title": "ID", "short": True, "value": latest_agent.id},
                    {"title": "Name", "short": True, "value": latest_agent.name},
                    {"title": "Model", "short": True, "value": latest_agent.model},
                    {
                        "title": "GOAT Enabled",
                        "short": True,
                        "value": str(latest_agent.goat_enabled),
                    },
                    {
                        "title": "CDP Enabled",
                        "short": True,
                        "value": str(latest_agent.cdp_enabled),
                    },
                    {
                        "title": "CDP Network",
                        "short": True,
                        "value": latest_agent.cdp_network_id or "Default",
                    },
                    {
                        "title": "Autonomous",
                        "short": True,
                        "value": str(latest_agent.autonomous_enabled),
                    },
                    {
                        "title": "Autonomous Interval",
                        "short": True,
                        "value": str(latest_agent.autonomous_minutes),
                    },
                    {
                        "title": "Twitter Entrypoint",
                        "short": True,
                        "value": str(latest_agent.twitter_entrypoint_enabled),
                    },
                    {
                        "title": "Telegram Entrypoint",
                        "short": True,
                        "value": str(latest_agent.telegram_entrypoint_enabled),
                    },
                    {
                        "title": "Twitter Skills",
                        "value": str(latest_agent.twitter_skills),
                    },
                    {
                        "title": "CDP Wallet Address",
                        "value": wallet_data.get("default_address_id"),
                    },
                ],
            }
        ],
    )

    return latest_agent, agent_data


@admin_router.post(
    "/agents", tags=["Agent"], status_code=201, operation_id="post_agent"
)
async def create_agent(
    agent: Agent = Body(Agent, description="Agent configuration"),
    subject: str = Depends(verify_jwt),
) -> AgentResponse:
    """Create or update an agent.

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
    return AgentResponse.from_agent(latest_agent, agent_data)


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
    agents = (await db.exec(select(Agent))).all()

    # Batch get agent data
    agent_ids = [agent.id for agent in agents]
    agent_data_list = (
        await db.exec(select(AgentData).where(AgentData.id.in_(agent_ids)))
    ).all()
    agent_data_map = {data.id: data for data in agent_data_list}

    # Convert to AgentResponse objects
    return [
        AgentResponse.from_agent(agent, agent_data_map.get(agent.id))
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
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Get a single agent by ID.

    **Path Parameters:**
    * `agent_id` - ID of the agent to retrieve

    **Returns:**
    * `AgentResponse` - Agent configuration with additional processed data

    **Raises:**
    * `HTTPException`:
        - 404: Agent not found
    """
    agent = (await db.exec(select(Agent).where(Agent.id == agent_id))).first()
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent with id {agent_id} not found",
        )

    # Get agent data
    agent_data = (
        await db.exec(select(AgentData).where(AgentData.id == agent_id))
    ).first()

    return AgentResponse.from_agent(agent, agent_data)


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
    "/agents/clean-memory",
    tags=["Agent"],
    status_code=201,
    dependencies=[Depends(verify_jwt)],
    operation_id="clean_agent_memory",
)
async def clean_memory(
    request: MemCleanRequest = Body(
        MemCleanRequest, description="Agent memory cleanup request"
    ),
    db: AsyncSession = Depends(get_db),
) -> str:
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

        return await clean_agent_memory(
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
    try:
        agent = await Agent.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        yaml_content = agent.to_yaml()
        return Response(
            content=yaml_content,
            media_type="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="{agent_id}.yaml"'},
        )
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Agent not found")
    except Exception as e:
        logger.error(f"Error exporting agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    try:
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

        # Ensure agent ID matches
        if yaml_data.get("id") != agent_id:
            raise HTTPException(
                status_code=400, detail="Agent ID in YAML does not match URL parameter"
            )

        # Create Agent instance from YAML
        try:
            agent = Agent(**yaml_data)
        except ValidationError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid agent configuration: {e}"
            )

        # Process the agent
        await _process_agent(
            agent, subject, slack_message="Agent Updated via YAML Import"
        )

        return "Agent import successful"

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
