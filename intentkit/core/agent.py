import logging
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text, update

from intentkit.clients.cdp import get_wallet_provider
from intentkit.config.config import config
from intentkit.core.template import render_agent
from intentkit.models.agent import (
    Agent,
    AgentCreate,
    AgentTable,
    AgentUpdate,
)
from intentkit.models.agent_data import AgentData, AgentQuotaTable
from intentkit.models.credit import (
    CreditAccount,
    CreditEventTable,
    EventType,
    OwnerType,
    UpstreamType,
)
from intentkit.models.db import get_session
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.slack_alert import send_slack_message

logger = logging.getLogger(__name__)


async def get_agent(agent_id: str) -> Agent | None:
    """Get an agent by ID and render with template if template_id exists.

    This function retrieves an agent from the database and applies template
    rendering if the agent has a template_id set.

    Args:
        agent_id: The unique identifier of the agent

    Returns:
        Agent | None: The agent with template applied if applicable, or None if not found
    """
    async with get_session() as db:
        item = await db.scalar(select(AgentTable).where(AgentTable.id == agent_id))
        if item is None:
            return None
        agent = Agent.model_validate(item)

    # If agent has a template_id, render it with the template
    if item.template_id:
        agent = await render_agent(agent)

    return agent


async def process_agent_wallet(
    agent: Agent, old_wallet_provider: str | None = None
) -> AgentData:
    """Process agent wallet initialization and validation.

    Args:
        agent: The agent that was created or updated
        old_wallet_provider: Previous wallet provider (None, "cdp", or "readonly")

    Returns:
        AgentData: The processed agent data

    Raises:
        IntentKitAPIError: If attempting to change between cdp and readonly providers
    """
    current_wallet_provider = agent.wallet_provider

    # 1. Check if changing between cdp and readonly (not allowed)
    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider != current_wallet_provider
    ):
        raise IntentKitAPIError(
            400,
            "WalletProviderChangeNotAllowed",
            "Cannot change wallet provider between cdp and readonly",
        )

    # 2. If wallet provider hasn't changed, return existing agent data
    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider == current_wallet_provider
    ):
        return await AgentData.get(agent.id)

    # 3. For new agents (old_wallet_provider is None), check if wallet already exists
    agent_data = await AgentData.get(agent.id)
    if agent_data.evm_wallet_address:
        return agent_data

    # 4. Initialize wallet based on provider type
    if config.cdp_api_key_id and current_wallet_provider == "cdp":
        await get_wallet_provider(agent)
        agent_data = await AgentData.get(agent.id)
    elif current_wallet_provider == "readonly":
        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": agent.readonly_wallet_address,
            },
        )

    return agent_data


def send_agent_notification(agent: Agent, agent_data: AgentData, message: str) -> None:
    """Send a notification about agent creation or update.

    Args:
        agent: The agent that was created or updated
        agent_data: The agent data to update
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
                    {"title": "ID", "short": True, "value": agent.id},
                    {"title": "Name", "short": True, "value": agent.name},
                    {"title": "Model", "short": True, "value": agent.model},
                    {
                        "title": "Network",
                        "short": True,
                        "value": agent.network_id or "Not Set",
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
                        "title": "Wallet Address",
                        "value": agent_data.evm_wallet_address,
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
        latest_agent, existing_agent.wallet_provider
    )
    send_agent_notification(latest_agent, agent_data, "Agent Overridden Deployed")

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


async def agent_action_cost(agent_id: str) -> dict[str, Decimal]:
    """
    Calculate various action cost metrics for an agent based on past three days of credit events.

    Metrics calculated:
    - avg_action_cost: average cost per action
    - min_action_cost: minimum cost per action
    - max_action_cost: maximum cost per action
    - low_action_cost: average cost of the lowest 20% of actions
    - medium_action_cost: average cost of the middle 60% of actions
    - high_action_cost: average cost of the highest 20% of actions

    Args:
        agent_id: ID of the agent

    Returns:
        dict[str, Decimal]: Dictionary containing all calculated cost metrics
    """
    start_time = time.time()
    default_value = Decimal("0")

    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    async with get_session() as session:
        # Calculate the date 3 days ago from now
        three_days_ago = datetime.now(UTC) - timedelta(days=3)

        # First, count the number of distinct start_message_ids to determine if we have enough data
        count_query = select(
            func.count(func.distinct(CreditEventTable.start_message_id))
        ).where(
            CreditEventTable.agent_id == agent_id,
            CreditEventTable.created_at >= three_days_ago,
            CreditEventTable.user_id != agent.owner,
            CreditEventTable.upstream_type == UpstreamType.EXECUTOR,
            CreditEventTable.event_type.in_([EventType.MESSAGE, EventType.SKILL_CALL]),
            CreditEventTable.start_message_id.is_not(None),
        )

        result = await session.execute(count_query)
        record_count = result.scalar_one()

        # If we have fewer than 10 records, return default values
        if record_count < 10:
            time_cost = time.time() - start_time
            logger.info(
                f"agent_action_cost for {agent_id}: using default values (insufficient records: {record_count}) timeCost={time_cost:.3f}s"
            )
            return {
                "avg_action_cost": default_value,
                "min_action_cost": default_value,
                "max_action_cost": default_value,
                "low_action_cost": default_value,
                "medium_action_cost": default_value,
                "high_action_cost": default_value,
            }

        # Calculate the basic metrics (avg, min, max) directly in PostgreSQL
        basic_metrics_query = text("""
            WITH action_sums AS (
                SELECT start_message_id, SUM(total_amount) AS action_cost
                FROM credit_events
                WHERE agent_id = :agent_id
                  AND created_at >= :three_days_ago
                  AND upstream_type = :upstream_type
                  AND event_type IN (:event_type_message, :event_type_skill_call)
                  AND start_message_id IS NOT NULL
                GROUP BY start_message_id
            )
            SELECT
                AVG(action_cost) AS avg_cost,
                MIN(action_cost) AS min_cost,
                MAX(action_cost) AS max_cost
            FROM action_sums
        """)

        # Calculate the percentile-based metrics (low, medium, high) using window functions
        percentile_metrics_query = text("""
            WITH action_sums AS (
                SELECT
                    start_message_id,
                    SUM(total_amount) AS action_cost,
                    NTILE(5) OVER (ORDER BY SUM(total_amount)) AS quintile
                FROM credit_events
                WHERE agent_id = :agent_id
                  AND created_at >= :three_days_ago
                  AND upstream_type = :upstream_type
                  AND event_type IN (:event_type_message, :event_type_skill_call)
                  AND start_message_id IS NOT NULL
                GROUP BY start_message_id
            )
            SELECT
                (SELECT AVG(action_cost) FROM action_sums WHERE quintile = 1) AS low_cost,
                (SELECT AVG(action_cost) FROM action_sums WHERE quintile IN (2, 3, 4)) AS medium_cost,
                (SELECT AVG(action_cost) FROM action_sums WHERE quintile = 5) AS high_cost
            FROM action_sums
            LIMIT 1
        """)

        # Bind parameters to prevent SQL injection and ensure correct types
        params = {
            "agent_id": agent_id,
            "three_days_ago": three_days_ago,
            "upstream_type": UpstreamType.EXECUTOR,
            "event_type_message": EventType.MESSAGE,
            "event_type_skill_call": EventType.SKILL_CALL,
        }

        # Execute the basic metrics query
        basic_result = await session.execute(basic_metrics_query, params)
        basic_row = basic_result.fetchone()

        # Execute the percentile metrics query
        percentile_result = await session.execute(percentile_metrics_query, params)
        percentile_row = percentile_result.fetchone()

        # If no results, return the default values
        if not basic_row or basic_row[0] is None:
            time_cost = time.time() - start_time
            logger.info(
                f"agent_action_cost for {agent_id}: using default values (no action costs found) timeCost={time_cost:.3f}s"
            )
            return {
                "avg_action_cost": default_value,
                "min_action_cost": default_value,
                "max_action_cost": default_value,
                "low_action_cost": default_value,
                "medium_action_cost": default_value,
                "high_action_cost": default_value,
            }

        # Extract and convert the values to Decimal for consistent precision
        avg_cost = Decimal(str(basic_row[0] or 0)).quantize(Decimal("0.0001"))
        min_cost = Decimal(str(basic_row[1] or 0)).quantize(Decimal("0.0001"))
        max_cost = Decimal(str(basic_row[2] or 0)).quantize(Decimal("0.0001"))

        # Extract percentile-based metrics
        low_cost = (
            Decimal(str(percentile_row[0] or 0)).quantize(Decimal("0.0001"))
            if percentile_row and percentile_row[0] is not None
            else default_value
        )
        medium_cost = (
            Decimal(str(percentile_row[1] or 0)).quantize(Decimal("0.0001"))
            if percentile_row and percentile_row[1] is not None
            else default_value
        )
        high_cost = (
            Decimal(str(percentile_row[2] or 0)).quantize(Decimal("0.0001"))
            if percentile_row and percentile_row[2] is not None
            else default_value
        )

        # Create the result dictionary
        result = {
            "avg_action_cost": avg_cost,
            "min_action_cost": min_cost,
            "max_action_cost": max_cost,
            "low_action_cost": low_cost,
            "medium_action_cost": medium_cost,
            "high_action_cost": high_cost,
        }

        time_cost = time.time() - start_time
        logger.info(
            f"agent_action_cost for {agent_id}: avg={avg_cost}, min={min_cost}, max={max_cost}, "
            f"low={low_cost}, medium={medium_cost}, high={high_cost} "
            f"(records: {record_count}) timeCost={time_cost:.3f}s"
        )

        return result


async def _iterate_agent_id_batches(
    batch_size: int = 100,
) -> AsyncGenerator[list[str], None]:
    """Yield agent IDs in ascending batches to limit memory usage."""

    last_id: str | None = None
    while True:
        async with get_session() as session:
            query = select(AgentTable.id).order_by(AgentTable.id)

            if last_id:
                query = query.where(AgentTable.id > last_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            agent_ids = [row[0] for row in result]

        if not agent_ids:
            break

        yield agent_ids
        last_id = agent_ids[-1]


async def update_agent_action_cost(batch_size: int = 100) -> None:
    """
    Update action costs for all agents.

    This function processes agents in batches of 100 to avoid memory issues.
    For each agent, it calculates various action cost metrics:
    - avg_action_cost: average cost per action
    - min_action_cost: minimum cost per action
    - max_action_cost: maximum cost per action
    - low_action_cost: average cost of the lowest 20% of actions
    - medium_action_cost: average cost of the middle 60% of actions
    - high_action_cost: average cost of the highest 20% of actions

    It then updates the corresponding record in the agent_quotas table.
    """
    logger.info("Starting update of agent average action costs")
    start_time = time.time()
    total_updated = 0

    async for agent_ids in _iterate_agent_id_batches(batch_size):
        logger.info(
            "Processing batch of %s agents starting with ID %s",
            len(agent_ids),
            agent_ids[0],
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                costs = await agent_action_cost(agent_id)

                async with get_session() as session:
                    update_stmt = (
                        update(AgentQuotaTable)
                        .where(AgentQuotaTable.id == agent_id)
                        .values(
                            avg_action_cost=costs["avg_action_cost"],
                            min_action_cost=costs["min_action_cost"],
                            max_action_cost=costs["max_action_cost"],
                            low_action_cost=costs["low_action_cost"],
                            medium_action_cost=costs["medium_action_cost"],
                            high_action_cost=costs["high_action_cost"],
                        )
                    )
                    await session.execute(update_stmt)
                    await session.commit()

                total_updated += 1
            except Exception as e:  # pragma: no cover - log path only
                logger.error(
                    "Error updating action costs for agent %s: %s", agent_id, str(e)
                )

        batch_time = time.time() - batch_start_time
        logger.info("Completed batch in %.3fs", batch_time)

    total_time = time.time() - start_time
    logger.info(
        "Finished updating action costs for %s agents in %.3fs",
        total_updated,
        total_time,
    )


async def update_agents_account_snapshot(batch_size: int = 100) -> None:
    """Refresh the cached credit account snapshot for every agent."""

    logger.info("Starting update of agent account snapshots")
    start_time = time.time()
    total_updated = 0

    async for agent_ids in _iterate_agent_id_batches(batch_size):
        logger.info(
            "Processing snapshot batch of %s agents starting with ID %s",
            len(agent_ids),
            agent_ids[0],
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                async with get_session() as session:
                    account = await CreditAccount.get_or_create_in_session(
                        session, OwnerType.AGENT, agent_id
                    )
                    await session.execute(
                        update(AgentTable)
                        .where(AgentTable.id == agent_id)
                        .values(
                            account_snapshot=account.model_dump(mode="json"),
                        )
                    )
                    await session.commit()

                total_updated += 1
            except Exception as exc:  # pragma: no cover - log path only
                logger.error(
                    "Error updating account snapshot for agent %s: %s",
                    agent_id,
                    exc,
                )

        batch_time = time.time() - batch_start_time
        logger.info("Completed snapshot batch in %.3fs", batch_time)

    total_time = time.time() - start_time
    logger.info(
        "Finished updating account snapshots for %s agents in %.3fs",
        total_updated,
        total_time,
    )


async def update_agents_assets(batch_size: int = 100) -> None:
    """Refresh cached asset information for all agents."""

    from intentkit.core.asset import agent_asset

    logger.info("Starting update of agent assets")
    start_time = time.time()
    total_updated = 0

    async for agent_ids in _iterate_agent_id_batches(batch_size):
        logger.info(
            "Processing asset batch of %s agents starting with ID %s",
            len(agent_ids),
            agent_ids[0],
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                assets = await agent_asset(agent_id)
            except IntentKitAPIError as exc:  # pragma: no cover - log path only
                logger.warning(
                    "Skipping asset update for agent %s due to API error: %s",
                    agent_id,
                    exc,
                )
                continue
            except Exception as exc:  # pragma: no cover - log path only
                logger.error("Error retrieving assets for agent %s: %s", agent_id, exc)
                continue

            try:
                async with get_session() as session:
                    await session.execute(
                        update(AgentTable)
                        .where(AgentTable.id == agent_id)
                        .values(assets=assets.model_dump(mode="json"))
                    )
                    await session.commit()

                total_updated += 1
            except Exception as exc:  # pragma: no cover - log path only
                logger.error(
                    "Error updating asset cache for agent %s: %s", agent_id, exc
                )

        batch_time = time.time() - batch_start_time
        logger.info("Completed asset batch in %.3fs", batch_time)

    total_time = time.time() - start_time
    logger.info(
        "Finished updating assets for %s agents in %.3fs",
        total_updated,
        total_time,
    )


async def update_agents_statistics(
    *, end_time: datetime | None = None, batch_size: int = 100
) -> None:
    """Refresh cached statistics for every agent."""

    from intentkit.core.statistics import get_agent_statistics

    if end_time is None:
        end_time = datetime.now(UTC)
    elif end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=UTC)
    else:
        end_time = end_time.astimezone(UTC)

    logger.info("Starting update of agent statistics using end_time %s", end_time)
    start_time = time.time()
    total_updated = 0

    async for agent_ids in _iterate_agent_id_batches(batch_size):
        logger.info(
            "Processing statistics batch of %s agents starting with ID %s",
            len(agent_ids),
            agent_ids[0],
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                statistics = await get_agent_statistics(agent_id, end_time=end_time)
            except Exception as exc:  # pragma: no cover - log path only
                logger.error(
                    "Error computing statistics for agent %s: %s", agent_id, exc
                )
                continue

            try:
                async with get_session() as session:
                    await session.execute(
                        update(AgentTable)
                        .where(AgentTable.id == agent_id)
                        .values(statistics=statistics.model_dump(mode="json"))
                    )
                    await session.commit()

                total_updated += 1
            except Exception as exc:  # pragma: no cover - log path only
                logger.error(
                    "Error updating statistics cache for agent %s: %s",
                    agent_id,
                    exc,
                )

        batch_time = time.time() - batch_start_time
        logger.info("Completed statistics batch in %.3fs", batch_time)

    total_time = time.time() - start_time
    logger.info(
        "Finished updating statistics for %s agents in %.3fs",
        total_updated,
        total_time,
    )
