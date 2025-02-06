"""Base class for all CryptoCompare tools."""

from abstracts.skill import IntentKitSkill
from abstracts.agent import AgentStoreABC
from abstracts.skill import SkillStoreABC
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone

class CryptoCompareBaseTool(IntentKitSkill):
    """Base class for CryptoCompare tools."""

    # A placeholder for a CryptoCompare client or configuration
    cryptocompare: object = Field(description="The CryptoCompare client or configuration")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type = Field(description="The input arguments schema")
    agent_id: str = Field(description="The ID of the agent")
    agent_store: AgentStoreABC = Field(description="The agent store for persisting data")
    skill_store: SkillStoreABC = Field(description="The skill store for persisting data")

    async def check_rate_limit(self, max_requests: int = 1, interval: int = 15) -> tuple[bool, str | None]:
        """Check if the rate limit has been exceeded."""
        rate_limit = await self.skill_store.get_agent_skill_data(self.agent_id, self.name, "rate_limit")
        current_time = datetime.now(tz=timezone.utc)
        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit.get("count") is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                return True, "Rate limit exceeded"
            else:
                rate_limit["count"] += 1
                await self.skill_store.save_agent_skill_data(self.agent_id, self.name, "rate_limit", rate_limit)
                return False, None
        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        await self.skill_store.save_agent_skill_data(self.agent_id, self.name, "rate_limit", new_rate_limit)
        return False, None

