from datetime import datetime, timedelta, timezone
from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.exception import RateLimitExceeded
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class TwitterBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "twitter"

    async def check_rate_limit(
        self, agent_id: str, max_requests: int = 1, interval: int = 15
    ) -> None:
        """Check if the rate limit has been exceeded.

        Args:
            agent_id: The ID of the agent.
            max_requests: Maximum number of requests allowed within the rate limit window.
            interval: Time interval in minutes for the rate limit window.

        Raises:
            RateLimitExceeded: If the rate limit has been exceeded.
        """
        rate_limit = await self.skill_store.get_agent_skill_data(
            agent_id, self.name, "rate_limit"
        )

        current_time = datetime.now(tz=timezone.utc)

        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit["count"] is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                raise RateLimitExceeded("Rate limit exceeded")

            rate_limit["count"] += 1
            await self.skill_store.save_agent_skill_data(
                agent_id, self.name, "rate_limit", rate_limit
            )

            return

        # If no rate limit exists or it has expired, create a new one
        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        await self.skill_store.save_agent_skill_data(
            agent_id, self.name, "rate_limit", new_rate_limit
        )
        return
