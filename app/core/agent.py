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


async def agent_avg_action_cost(agent_id: str) -> Decimal:
    """
    Calculate the average action cost for an agent based on past three days of credit events.

    This function analyzes credit events for the specified agent from the past three days,
    filtering for event types MESSAGE and SKILL_CALL with upstream type EXECUTOR.
    It groups by start_message_id and sums the total amount for each action.

    The counting and averaging is performed directly in the database to handle large record sets.

    Args:
        agent_id: ID of the agent

    Returns:
        Decimal: Average cost per action, or 1.0 if there are fewer than 10 records
    """
    start_time = time.time()

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

        # If we have fewer than 10 records, return a fixed value of 1
        if record_count < 10:
            time_cost = time.time() - start_time
            logger.info(
                f"agent_avg_action_cost for {agent_id}: result=1.0 (insufficient records: {record_count}) timeCost={time_cost:.3f}s"
            )
            return Decimal("1.0")

        # Calculate the average directly in PostgreSQL using a CTE (Common Table Expression)
        # This avoids loading all data into memory
        avg_query = text("""
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
            SELECT AVG(action_cost) AS avg_cost
            FROM action_sums
        """)

        # Bind parameters to prevent SQL injection and ensure correct types
        result = await session.execute(
            avg_query,
            {
                "agent_id": agent_id,
                "three_days_ago": three_days_ago,
                "upstream_type": UpstreamType.EXECUTOR,
                "event_type_message": EventType.MESSAGE,
                "event_type_skill_call": EventType.SKILL_CALL,
            },
        )

        # Get the result
        row = result.fetchone()
        avg_cost = row[0] if row and row[0] is not None else None

        # If no results, return the default value
        if avg_cost is None:
            time_cost = time.time() - start_time
            logger.info(
                f"agent_avg_action_cost for {agent_id}: result=1.0 (no action costs found) timeCost={time_cost:.3f}s"
            )
            return Decimal("1.0")

        # Convert to Decimal for consistent precision
        final_cost = Decimal(str(avg_cost)).quantize(Decimal("0.0001"))
        time_cost = time.time() - start_time
        logger.info(
            f"agent_avg_action_cost for {agent_id}: result={final_cost} (records: {record_count}) timeCost={time_cost:.3f}s"
        )

        return final_cost
