import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent import Agent, AgentCreate, AgentUpdate
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

from .notifications import send_agent_notification
from .queries import get_agent, get_agent_by_id_or_slug
from .wallet import process_agent_wallet

logger = logging.getLogger(__name__)


async def _validate_slug_unique(
    slug: str, exclude_agent_id: str | None, db: AsyncSession
) -> None:
    """Check that a slug is not already in use by another agent."""
    query = select(AgentTable.id).where(AgentTable.slug == slug)
    if exclude_agent_id:
        query = query.where(AgentTable.id != exclude_agent_id)
    existing = await db.scalar(query)
    if existing:
        raise IntentKitAPIError(
            400, "SlugAlreadyExists", f"Slug '{slug}' is already in use"
        )


async def _validate_sub_agents(sub_agents: list[str]) -> None:
    """Validate that all sub-agents exist and have a purpose defined."""
    for agent_ref in sub_agents:
        target = await get_agent_by_id_or_slug(agent_ref)
        if not target:
            raise IntentKitAPIError(
                400,
                "InvalidSubAgent",
                f"Sub-agent '{agent_ref}' not found",
            )
        if not target.purpose:
            raise IntentKitAPIError(
                400,
                "InvalidSubAgent",
                f"Sub-agent '{agent_ref}' must have a purpose defined",
            )


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

    # Validate autonomous schedule settings if present
    if "autonomous" in agent.model_dump(exclude_unset=True):
        agent.validate_autonomous_schedule()

    # Validate sub-agents if present
    if agent.sub_agents:
        await _validate_sub_agents(agent.sub_agents)

    # Slug immutability check
    if (
        existing_agent.slug
        and agent.slug is not None
        and agent.slug != existing_agent.slug
    ):
        raise IntentKitAPIError(400, "SlugImmutable", "Slug cannot be changed once set")

    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent:
            raise IntentKitAPIError(
                status_code=404,
                key="AgentNotFound",
                message="Agent not found",
            )

        # Slug uniqueness check
        if agent.slug:
            await _validate_slug_unique(agent.slug, agent_id, db)

        # update
        update_data = agent.model_dump()
        if "autonomous" in update_data:
            update_data["autonomous"] = agent.normalize_autonomous_statuses(
                update_data["autonomous"]
            )
        if "skills" in update_data and update_data["skills"]:
            from intentkit.core.manager.service import sanitize_skills

            update_data["skills"] = sanitize_skills(update_data["skills"])
        for key, value in update_data.items():
            setattr(db_agent, key, value)
        # version
        db_agent.version = agent.hash()
        db_agent.deployed_at = func.now()
        await db.commit()
        await db.refresh(db_agent)
        latest_agent = Agent.model_validate(db_agent)

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

    # Validate autonomous schedule settings if present
    if "autonomous" in agent.model_dump(exclude_unset=True):
        agent.validate_autonomous_schedule()

    # Validate sub-agents if present in update
    update_fields = agent.model_dump(exclude_unset=True)
    if "sub_agents" in update_fields and update_fields["sub_agents"]:
        await _validate_sub_agents(update_fields["sub_agents"])

    # Slug immutability check
    if (
        existing_agent.slug
        and "slug" in update_fields
        and update_fields["slug"] != existing_agent.slug
    ):
        raise IntentKitAPIError(400, "SlugImmutable", "Slug cannot be changed once set")

    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent:
            raise IntentKitAPIError(
                status_code=404,
                key="AgentNotFound",
                message="Agent not found",
            )

        # Slug uniqueness check
        slug_value = update_fields.get("slug")
        if slug_value:
            await _validate_slug_unique(slug_value, agent_id, db)

        # update
        update_data = update_fields
        if "autonomous" in update_data:
            update_data["autonomous"] = agent.normalize_autonomous_statuses(
                update_data["autonomous"]
            )
        if "skills" in update_data and update_data["skills"]:
            from intentkit.core.manager.service import sanitize_skills

            update_data["skills"] = sanitize_skills(update_data["skills"])
        for key, value in update_data.items():
            setattr(db_agent, key, value)
        db_agent.version = agent.hash()
        db_agent.deployed_at = func.now()
        await db.commit()
        await db.refresh(db_agent)
        latest_agent = Agent.model_validate(db_agent)

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
    if agent.upstream_id:
        async with get_session() as db:
            existing = await db.scalar(
                select(AgentTable).where(AgentTable.upstream_id == agent.upstream_id)
            )
            if existing:
                raise IntentKitAPIError(
                    status_code=400,
                    key="BadRequest",
                    message="Agent with this upstream ID already exists",
                )

    # Validate autonomous schedule settings if present
    if agent.autonomous:
        agent.validate_autonomous_schedule()

    # Validate sub-agents if present
    if agent.sub_agents:
        await _validate_sub_agents(agent.sub_agents)

    # Validate skills configuration
    if agent.skills:
        from intentkit.core.manager.service import validate_skills

        validate_skills(agent.skills)

    async with get_session() as db:
        try:
            # Slug uniqueness check
            if agent.slug:
                await _validate_slug_unique(agent.slug, None, db)

            create_data = agent.model_dump()
            if "autonomous" in create_data:
                create_data["autonomous"] = agent.normalize_autonomous_statuses(
                    create_data["autonomous"]
                )
            db_agent = AgentTable(**create_data)
            db_agent.version = agent.hash()
            db_agent.deployed_at = func.now()
            db.add(db_agent)
            await db.commit()
            await db.refresh(db_agent)
            latest_agent = Agent.model_validate(db_agent)
        except IntegrityError:
            await db.rollback()
            raise IntentKitAPIError(
                status_code=400,
                key="AgentExists",
                message=f"Agent with ID '{agent.id}' already exists",
            )

    agent_data = await process_agent_wallet(latest_agent)
    send_agent_notification(latest_agent, agent_data, "Agent Deployed")

    if latest_agent.team_id:
        try:
            from intentkit.core.team.subscription import auto_subscribe_team

            await auto_subscribe_team(latest_agent.team_id, latest_agent.id)
        except Exception:
            logger.exception(
                "Failed to auto-subscribe team %s to agent %s",
                latest_agent.team_id,
                latest_agent.id,
            )

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
