from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, func, select

from app.config.config import config
from app.core.engine import initialize_agent
from models.agent import Agent, AgentData, AgentResponse
from models.db import get_db
from utils.middleware import create_jwt_middleware
from utils.slack_alert import send_slack_message

admin_router = APIRouter()


# Create JWT middleware with admin config
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)


@admin_router.post("/agents", tags=["Agent"], status_code=201)
async def create_agent(
    agent: Agent = Body(Agent, description="Agent configuration"),
    subject: str = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Create or update an agent.

    This endpoint:
    1. Validates agent ID format
    2. Creates or updates agent configuration
    3. Reinitializes agent if already in cache
    4. Masks sensitive data in response

    Args:
      - agent: Agent configuration
      - db: Database session

    Returns:
      - AgentResponse: Updated agent configuration with additional processed data

    Raises:
      - HTTPException:
          - 400: Invalid agent ID format
          - 500: Database error
    """
    if subject:
        agent.owner = subject

    # Get the latest agent from create_or_update
    latest_agent = agent.create_or_update(db)

    # Send Slack notification
    total_agents = db.exec(select(func.count()).select_from(Agent)).one()
    send_slack_message(
        "Agent created or updated:",
        attachments=[
            {
                "color": "good",
                "fields": [
                    {"title": "ENV", "short": True, "value": config.env},
                    {"title": "Total", "short": True, "value": total_agents},
                    {"title": "ID", "short": True, "value": latest_agent.id},
                    {"title": "Name", "short": True, "value": latest_agent.name},
                    {"title": "Model", "short": True, "value": latest_agent.model},
                    {
                        "title": "Enso Enabled",
                        "short": True,
                        "value": str(latest_agent.enso_enabled),
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
                ],
            }
        ],
    )

    # Mask sensitive data in response
    latest_agent.cdp_wallet_data = "forbidden"
    if latest_agent.skill_sets is not None:
        for key in latest_agent.skill_sets:
            latest_agent.skill_sets[key] = {}

    # TODO: change here when multiple instances deploy
    initialize_agent(agent.id)

    # Get agent data
    agent_data = db.exec(
        select(AgentData).where(AgentData.id == latest_agent.id)
    ).first()

    # Convert to AgentResponse
    return AgentResponse.from_agent(latest_agent, agent_data)


@admin_router.get("/agents", tags=["Agent"], dependencies=[Depends(verify_jwt)])
async def get_agents(db: Session = Depends(get_db)) -> list[AgentResponse]:
    """Get all agents with their quota information.

    Args:
        db: Database session

    Returns:
        list[AgentResponse]: List of agents with their quota information and additional processed data
    """
    # Query all agents first
    agents = db.exec(select(Agent)).all()

    # Batch get agent data
    agent_ids = [agent.id for agent in agents]
    agent_data_list = db.exec(
        select(AgentData).where(AgentData.id.in_(agent_ids))
    ).all()
    agent_data_map = {data.id: data for data in agent_data_list}

    # Convert to AgentResponse objects
    return [
        AgentResponse.from_agent(agent, agent_data_map.get(agent.id))
        for agent in agents
    ]


@admin_router.get(
    "/agents/{agent_id}", tags=["Agent"], dependencies=[Depends(verify_jwt)]
)
async def get_agent(agent_id: str, db: Session = Depends(get_db)) -> AgentResponse:
    """Get a single agent by ID.

    Args:
        agent_id: ID of the agent to retrieve
        db: Database session

    Returns:
        AgentResponse: Agent configuration with additional processed data

    Raises:
        HTTPException:
            - 404: Agent not found
    """
    agent = db.exec(select(Agent).where(Agent.id == agent_id)).first()
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent with id {agent_id} not found",
        )

    # Get agent data
    agent_data = db.exec(select(AgentData).where(AgentData.id == agent_id)).first()

    return AgentResponse.from_agent(agent, agent_data)
