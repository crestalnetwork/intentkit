import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, select, text, update

from intentkit.models.agent import Agent, AgentAutonomous, AgentTable
from intentkit.models.agent_data import AgentQuotaTable
from intentkit.models.credit import CreditEventTable, EventType, UpstreamType
from intentkit.models.db import get_session
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def agent_action_cost(agent_id: str) -> Dict[str, Decimal]:
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
        Dict[str, Decimal]: Dictionary containing all calculated cost metrics
    """
    start_time = time.time()
    default_value = Decimal("0")

    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    async with get_session() as session:
        # Calculate the date 3 days ago from now
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

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


async def update_agent_action_cost():
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
    batch_size = 100
    last_id = None
    total_updated = 0

    while True:
        # Get a batch of agent IDs ordered by ID
        async with get_session() as session:
            query = select(AgentTable.id).order_by(AgentTable.id)

            # Apply pagination if we have a last_id from previous batch
            if last_id:
                query = query.where(AgentTable.id > last_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            agent_ids = [row[0] for row in result]

            # If no more agents, we're done
            if not agent_ids:
                break

            # Update last_id for next batch
            last_id = agent_ids[-1]

        # Process this batch of agents
        logger.info(
            f"Processing batch of {len(agent_ids)} agents starting with ID {agent_ids[0]}"
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                # Calculate action costs for this agent
                costs = await agent_action_cost(agent_id)

                # Update the agent's quota record
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
            except Exception as e:
                logger.error(
                    f"Error updating action costs for agent {agent_id}: {str(e)}"
                )

        batch_time = time.time() - batch_start_time
        logger.info(f"Completed batch in {batch_time:.3f}s")

    total_time = time.time() - start_time
    logger.info(
        f"Finished updating action costs for {total_updated} agents in {total_time:.3f}s"
    )


async def list_autonomous_tasks(agent_id: str) -> List[AgentAutonomous]:
    """
    List all autonomous tasks for an agent.

    Args:
        agent_id: ID of the agent

    Returns:
        List[AgentAutonomous]: List of autonomous task configurations

    Raises:
        IntentKitAPIError: If agent is not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    if not agent.autonomous:
        return []

    return agent.autonomous


async def add_autonomous_task(agent_id: str, task: AgentAutonomous) -> AgentAutonomous:
    """
    Add a new autonomous task to an agent.

    Args:
        agent_id: ID of the agent
        task: Autonomous task configuration (id will be generated if not provided)

    Returns:
        AgentAutonomous: The created task with generated ID

    Raises:
        IntentKitAPIError: If agent is not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    # Get current autonomous tasks
    current_tasks = agent.autonomous or []
    if not isinstance(current_tasks, list):
        current_tasks = []

    # Add the new task
    current_tasks.append(task)

    # Convert all AgentAutonomous objects to dictionaries for JSON serialization
    serializable_tasks = [task_item.model_dump() for task_item in current_tasks]

    # Update the agent in the database
    async with get_session() as session:
        update_stmt = (
            update(AgentTable)
            .where(AgentTable.id == agent_id)
            .values(autonomous=serializable_tasks)
        )
        await session.execute(update_stmt)
        await session.commit()

    logger.info(f"Added autonomous task {task.id} to agent {agent_id}")
    return task


async def delete_autonomous_task(agent_id: str, task_id: str) -> None:
    """
    Delete an autonomous task from an agent.

    Args:
        agent_id: ID of the agent
        task_id: ID of the task to delete

    Raises:
        IntentKitAPIError: If agent is not found or task is not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    # Get current autonomous tasks
    current_tasks = agent.autonomous or []
    if not isinstance(current_tasks, list):
        current_tasks = []

    # Find and remove the task
    task_found = False
    updated_tasks = []
    for task_data in current_tasks:
        if task_data.id == task_id:
            task_found = True
            continue
        updated_tasks.append(task_data)

    if not task_found:
        raise IntentKitAPIError(
            404, "TaskNotFound", f"Autonomous task with ID {task_id} not found."
        )

    # Convert remaining AgentAutonomous objects to dictionaries for JSON serialization
    serializable_tasks = [task_item.model_dump() for task_item in updated_tasks]

    # Update the agent in the database
    async with get_session() as session:
        update_stmt = (
            update(AgentTable)
            .where(AgentTable.id == agent_id)
            .values(autonomous=serializable_tasks)
        )
        await session.execute(update_stmt)
        await session.commit()

    logger.info(f"Deleted autonomous task {task_id} from agent {agent_id}")


async def update_autonomous_task(
    agent_id: str, task_id: str, task_updates: dict
) -> AgentAutonomous:
    """
    Update an autonomous task for an agent.

    Args:
        agent_id: ID of the agent
        task_id: ID of the task to update
        task_updates: Dictionary containing fields to update

    Returns:
        AgentAutonomous: The updated task

    Raises:
        IntentKitAPIError: If agent is not found or task is not found
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise IntentKitAPIError(
            400, "AgentNotFound", f"Agent with ID {agent_id} does not exist."
        )

    # Get current autonomous tasks
    current_tasks: List[AgentAutonomous] = agent.autonomous or []

    # Find and update the task
    task_found = False
    updated_tasks: List[AgentAutonomous] = []
    updated_task = None

    for task_data in current_tasks:
        if task_data.id == task_id:
            task_found = True
            # Create a dictionary with current task data
            task_dict = task_data.model_dump()
            # Update with provided fields
            task_dict.update(task_updates)
            # Create new AgentAutonomous instance
            updated_task = AgentAutonomous.model_validate(task_dict)
            updated_tasks.append(updated_task)
        else:
            updated_tasks.append(task_data)

    if not task_found:
        raise IntentKitAPIError(
            404, "TaskNotFound", f"Autonomous task with ID {task_id} not found."
        )

    # Convert all AgentAutonomous objects to dictionaries for JSON serialization
    serializable_tasks = [task_item.model_dump() for task_item in updated_tasks]

    # Update the agent in the database
    async with get_session() as session:
        update_stmt = (
            update(AgentTable)
            .where(AgentTable.id == agent_id)
            .values(autonomous=serializable_tasks)
        )
        await session.execute(update_stmt)
        await session.commit()

    logger.info(f"Updated autonomous task {task_id} for agent {agent_id}")
    return updated_task
