import importlib
import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text, update

from intentkit.config.config import config
from intentkit.config.db import get_session
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
        template_module = importlib.import_module("intentkit.core.template")
        render_agent = template_module.render_agent
        agent = await render_agent(agent)

    return agent


async def process_agent_wallet(
    agent: Agent,
    old_wallet_provider: str | None = None,
    old_weekly_spending_limit: float | None = None,
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
    old_limit = (
        Decimal(str(old_weekly_spending_limit)).quantize(Decimal("0.000001"))
        if old_weekly_spending_limit is not None
        else None
    )
    new_limit = (
        Decimal(str(agent.weekly_spending_limit)).quantize(Decimal("0.000001"))
        if agent.weekly_spending_limit is not None
        else None
    )

    # 1. Check if changing between cdp and readonly (not allowed)
    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider != current_wallet_provider
    ):
        raise IntentKitAPIError(
            400,
            "WalletProviderChangeNotAllowed",
            "Cannot change wallet provider once set",
        )

    # 2. If wallet provider hasn't changed, return existing agent data
    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider == current_wallet_provider
    ):
        if current_wallet_provider in ("safe", "privy") and old_limit != new_limit:
            agent_data = await AgentData.get(agent.id)
            if agent_data.privy_wallet_data:
                # Only safe mode supports spending limits
                if current_wallet_provider == "safe":
                    from intentkit.clients.privy import create_privy_safe_wallet

                    try:
                        privy_wallet_data = json.loads(agent_data.privy_wallet_data)
                    except json.JSONDecodeError:
                        privy_wallet_data = {}

                    existing_privy_wallet_id = privy_wallet_data.get("privy_wallet_id")
                    existing_privy_wallet_address = privy_wallet_data.get(
                        "privy_wallet_address"
                    )

                    if existing_privy_wallet_id and existing_privy_wallet_address:
                        rpc_url: str | None = None
                        network_id = (
                            agent.network_id
                            or privy_wallet_data.get("network_id")
                            or "base-mainnet"
                        )
                        if config.chain_provider:
                            try:
                                chain_config = config.chain_provider.get_chain_config(
                                    network_id
                                )
                                rpc_url = chain_config.rpc_url
                            except Exception as e:
                                logger.warning(
                                    f"Failed to get RPC URL from chain provider: {e}"
                                )

                        wallet_data = await create_privy_safe_wallet(
                            agent_id=agent.id,
                            network_id=network_id,
                            rpc_url=rpc_url,
                            weekly_spending_limit_usdc=agent.weekly_spending_limit
                            if agent.weekly_spending_limit is not None
                            else 0.0,
                            existing_privy_wallet_id=existing_privy_wallet_id,
                            existing_privy_wallet_address=existing_privy_wallet_address,
                        )
                        agent_data = await AgentData.patch(
                            agent.id,
                            {
                                "evm_wallet_address": wallet_data[
                                    "smart_wallet_address"
                                ],
                                "privy_wallet_data": json.dumps(wallet_data),
                            },
                        )
                        return agent_data
        return await AgentData.get(agent.id)

    # 3. For new agents (old_wallet_provider is None), check if wallet already exists
    agent_data = await AgentData.get(agent.id)
    if agent_data.evm_wallet_address:
        return agent_data

    # 4. Initialize wallet based on provider type
    if config.cdp_api_key_id and current_wallet_provider == "cdp":
        from intentkit.clients.cdp import get_wallet_provider as get_cdp_wallet_provider

        await get_cdp_wallet_provider(agent)
        agent_data = await AgentData.get(agent.id)
    elif current_wallet_provider == "readonly":
        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": agent.readonly_wallet_address,
            },
        )
    elif current_wallet_provider == "safe":
        from intentkit.clients.privy import create_privy_safe_wallet

        # Get RPC URL from chain provider if available
        rpc_url: str | None = None
        network_id = agent.network_id or "base-mainnet"
        if config.chain_provider:
            try:
                chain_config = config.chain_provider.get_chain_config(network_id)
                rpc_url = chain_config.rpc_url
            except Exception as e:
                logger.warning(f"Failed to get RPC URL from chain provider: {e}")

        # Check for partial wallet creation (Privy wallet created but Safe failed)
        # This allows recovery without creating duplicate Privy wallets
        existing_privy_wallet_id: str | None = None
        existing_privy_wallet_address: str | None = None
        if agent_data.privy_wallet_data:
            try:
                partial_data = json.loads(agent_data.privy_wallet_data)
                existing_privy_wallet_id = partial_data.get("privy_wallet_id")
                existing_privy_wallet_address = partial_data.get("privy_wallet_address")
                if existing_privy_wallet_id and existing_privy_wallet_address:
                    logger.info(
                        f"Found partial Privy wallet data for agent {agent.id}, "
                        + f"attempting recovery with wallet {existing_privy_wallet_id}"
                    )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse existing privy_wallet_data: {e}")

        # Create Privy wallet first and save immediately to enable recovery
        if not existing_privy_wallet_id:
            from intentkit.clients.privy import PrivyClient

            privy_client = PrivyClient()
            if not agent.owner:
                raise IntentKitAPIError(
                    400,
                    "PrivyUserIdMissing",
                    "Agent owner (Privy user ID) is required for Privy wallets",
                )
            if not agent.owner.startswith("did:privy:"):
                raise IntentKitAPIError(
                    400,
                    "PrivyUserIdInvalid",
                    "Only Privy-authenticated users (did:privy:...) can create Privy wallets",
                )
            # Create a 1-of-N key quorum containing both the server's authorization key
            # and the user's ID. This allows either party to independently control the wallet.
            server_public_keys = privy_client.get_authorization_public_keys()
            owner_key_quorum_id = await privy_client.create_key_quorum(
                user_ids=[agent.owner],
                public_keys=server_public_keys if server_public_keys else None,
                authorization_threshold=1,  # Any single party can authorize
                display_name=f"intentkit:{agent.id[:40]}",
            )
            # Create wallet with key quorum as owner (not additional signer)
            # This enables both server and user to fully control the wallet
            privy_wallet = await privy_client.create_wallet(
                owner_key_quorum_id=owner_key_quorum_id,
            )
            existing_privy_wallet_id = privy_wallet.id
            existing_privy_wallet_address = privy_wallet.address

            # Save partial data immediately so we can recover if Safe deployment fails
            partial_wallet_data = {
                "privy_wallet_id": existing_privy_wallet_id,
                "privy_wallet_address": existing_privy_wallet_address,
                "owner_key_quorum_id": owner_key_quorum_id,
                "network_id": network_id,
                "status": "privy_created",
            }
            await AgentData.patch(
                agent.id,
                {"privy_wallet_data": json.dumps(partial_wallet_data)},
            )
            logger.info(
                f"Created Privy wallet {existing_privy_wallet_id} for agent {agent.id}"
            )

        wallet_data = await create_privy_safe_wallet(
            agent_id=agent.id,
            network_id=network_id,
            rpc_url=rpc_url,
            weekly_spending_limit_usdc=agent.weekly_spending_limit,
            existing_privy_wallet_id=existing_privy_wallet_id,
            existing_privy_wallet_address=existing_privy_wallet_address,
        )
        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": wallet_data["smart_wallet_address"],
                "privy_wallet_data": json.dumps(wallet_data),
            },
        )
    elif current_wallet_provider == "privy":
        from intentkit.clients.privy import PrivyClient

        # New privy-only mode: create just the privy wallet, no safe
        privy_client = PrivyClient()
        if not agent.owner:
            raise IntentKitAPIError(
                400,
                "PrivyUserIdMissing",
                "Agent owner (Privy user ID) is required for Privy wallets",
            )
        if not agent.owner.startswith("did:privy:"):
            raise IntentKitAPIError(
                400,
                "PrivyUserIdInvalid",
                "Only Privy-authenticated users (did:privy:...) can create Privy wallets",
            )

        # Create a 1-of-N key quorum containing both the server's authorization key
        # and the user's ID. This allows either party to independently control the wallet.
        server_public_keys = privy_client.get_authorization_public_keys()
        owner_key_quorum_id = await privy_client.create_key_quorum(
            user_ids=[agent.owner],
            public_keys=server_public_keys if server_public_keys else None,
            authorization_threshold=1,  # Any single party can authorize
            display_name=f"intentkit:{agent.id[:40]}",
        )

        # Create wallet with key quorum as owner
        privy_wallet = await privy_client.create_wallet(
            owner_key_quorum_id=owner_key_quorum_id,
        )

        # Store wallet data - for privy-only mode, we use the privy wallet address directly
        wallet_data = {
            "privy_wallet_id": privy_wallet.id,
            "privy_wallet_address": privy_wallet.address,
            "owner_key_quorum_id": owner_key_quorum_id,
            "network_id": agent.network_id or "base-mainnet",
            "provider": "privy",
            "status": "created",
        }

        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": privy_wallet.address,  # Use privy wallet address directly
                "privy_wallet_data": json.dumps(wallet_data),
            },
        )
        logger.info(
            f"Created Privy-only wallet {privy_wallet.id} for agent {agent.id}, address: {privy_wallet.address}"
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
    asset_module = importlib.import_module("intentkit.core.asset")
    agent_asset = asset_module.agent_asset

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
