import logging

from intentkit.models.agent import Agent, AgentCreate, AgentUpdate
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

from .notifications import send_agent_notification
from .queries import get_agent
from .wallet import process_agent_wallet

logger = logging.getLogger(__name__)


async def override_agent(
    agent_id: str, agent: AgentUpdate, owner: str | None = None
) -> tuple[Agent, AgentData]:
    """Override an existing agent with new configuration.

    This function updates an existing agent with the provided configuration.
    If some fields are not provided, they will be reset to default values.

    Args:
        agent_id: ID of the agent to override
        agent: Agent update configuration containing the new settings
        owner: Optional owner for permission validation

    Returns:
        tuple[Agent, AgentData]: Updated agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 404: Agent not found
            - 403: Permission denied (if owner mismatch)
            - 400: Invalid configuration or wallet provider change
    """
    existing_agent = await get_agent(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent with ID '{agent_id}' not found",
        )
    if owner and owner != existing_agent.owner:
        raise IntentKitAPIError(403, "Forbidden", "forbidden")

    # Update agent
    latest_agent = await agent.override(agent_id)
    agent_data = await process_agent_wallet(
        latest_agent,
        existing_agent.wallet_provider,
        existing_agent.weekly_spending_limit,
    )
    send_agent_notification(latest_agent, agent_data, "Agent Overridden Deployed")

    return latest_agent, agent_data


async def patch_agent(
    agent_id: str, agent: AgentUpdate, owner: str | None = None
) -> tuple[Agent, AgentData]:
    """Patch an existing agent with partial updates.

    This function updates an existing agent with only the fields that are provided.
    Fields that are not specified will remain unchanged.

    Args:
        agent_id: ID of the agent to patch
        agent: Agent update configuration containing only the fields to update
        owner: Optional owner for permission validation

    Returns:
        tuple[Agent, AgentData]: Updated agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 404: Agent not found
            - 403: Permission denied (if owner mismatch)
            - 400: Invalid configuration or wallet provider change
    """
    existing_agent = await get_agent(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent with ID '{agent_id}' not found",
        )
    if owner and owner != existing_agent.owner:
        raise IntentKitAPIError(403, "Forbidden", "forbidden")

    # Update agent with only provided fields
    latest_agent = await agent.update(agent_id)
    agent_data = await process_agent_wallet(
        latest_agent,
        existing_agent.wallet_provider,
        existing_agent.weekly_spending_limit,
    )
    send_agent_notification(latest_agent, agent_data, "Agent Patched")

    return latest_agent, agent_data


async def create_agent(agent: AgentCreate) -> tuple[Agent, AgentData]:
    """Create a new agent with the provided configuration.

    This function creates a new agent instance with the given configuration,
    initializes its wallet, and sends a notification about the creation.

    Args:
        agent: Agent creation configuration containing all necessary settings

    Returns:
        tuple[Agent, AgentData]: Created agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 400: Agent with upstream ID already exists or invalid configuration
            - 500: Database error or wallet initialization failure
    """
    if not agent.owner:
        agent.owner = "system"
    # Check for existing agent by upstream_id, forward compatibility, raise error after 3.0
    existing = await agent.get_by_upstream_id()
    if existing:
        raise IntentKitAPIError(
            status_code=400,
            key="BadRequest",
            message="Agent with this upstream ID already exists",
        )

    # Create new agent
    latest_agent = await agent.create()
    agent_data = await process_agent_wallet(latest_agent)
    send_agent_notification(latest_agent, agent_data, "Agent Deployed")

    return latest_agent, agent_data


async def deploy_agent(
    agent_id: str, agent: AgentUpdate, owner: str | None = None
) -> tuple[Agent, AgentData]:
    """Deploy an agent by first attempting to override, then creating if not found.

    This function first tries to override an existing agent. If the agent is not found
    (404 error), it will create a new agent instead.

    Args:
        agent_id: ID of the agent to deploy
        agent: Agent configuration data
        owner: Optional owner for the agent

    Returns:
        tuple[Agent, AgentData]: Deployed agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 400: Invalid agent configuration or upstream ID conflict
            - 403: Permission denied (if owner mismatch)
            - 500: Database error
    """
    try:
        # First try to override the existing agent
        return await override_agent(agent_id, agent, owner)
    except IntentKitAPIError as e:
        # If agent not found (404), create a new one
        if e.status_code == 404:
            new_agent = AgentCreate.model_validate(agent)
            new_agent.id = agent_id
            new_agent.owner = owner
            return await create_agent(new_agent)
        else:
            # Re-raise other errors
            raise
