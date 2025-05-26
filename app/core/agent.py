import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func, select, text

from abstracts.agent import AgentStoreABC
from models.agent import Agent, AgentData, AgentQuota
from models.credit import CreditEventTable, EventType, UpstreamType
from models.db import get_session

logger = logging.getLogger(__name__)


class AgentStore(AgentStoreABC):
    """Implementation of agent data storage operations.

    This class provides concrete implementations for storing and retrieving
    agent-related data.

    Args:
        agent_id: ID of the agent
    """

    def __init__(self, agent_id: str) -> None:
        """Initialize the agent store.

        Args:
            agent_id: ID of the agent
        """
        super().__init__(agent_id)

    async def get_config(self) -> Optional[Agent]:
        """Get agent configuration.

        Returns:
            Agent configuration if found, None otherwise
        """
        return await Agent.get(self.agent_id)

    async def get_data(self) -> Optional[AgentData]:
        """Get additional agent data.

        Returns:
            Agent data if found, None otherwise
        """
        return await AgentData.get(self.agent_id)

    async def set_data(self, data: Dict) -> None:
        """Update agent data.

        Args:
            data: Dictionary containing fields to update
        """
        await AgentData.patch(self.agent_id, data)

    async def get_quota(self) -> Optional[AgentQuota]:
        """Get agent quota information.

        Returns:
            Agent quota if found, None otherwise
        """
        return await AgentQuota.get(self.agent_id)


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
    default_value = Decimal("1.0")

    async with get_session() as session:
        # Calculate the date 3 days ago from now
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

        # First, count the number of distinct start_message_ids to determine if we have enough data
        count_query = select(
            func.count(func.distinct(CreditEventTable.start_message_id))
        ).where(
            CreditEventTable.agent_id == agent_id,
            CreditEventTable.created_at >= three_days_ago,
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
