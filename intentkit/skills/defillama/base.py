"""Base class for all DeFi Llama tools."""

from datetime import datetime, timedelta, timezone
from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.defillama.config.chains import (
    get_chain_from_alias,
)

DEFILLAMA_BASE_URL = "https://api.llama.fi"


class DefiLlamaBaseTool(IntentKitSkill):
    """Base class for DeFi Llama tools.

    This class provides common functionality for all DeFi Llama API tools:
    - Rate limiting
    - State management
    - Chain validation
    - Error handling
    """

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
    base_url: str = Field(
        default=DEFILLAMA_BASE_URL, description="Base URL for DeFi Llama API"
    )

    @property
    def category(self) -> str:
        return "defillama"

    async def check_rate_limit(
        self, context: AgentContext, max_requests: int = 30, interval: int = 5
    ) -> tuple[bool, str | None]:
        """Check if the rate limit has been exceeded.

        Args:
            context: Skill context
            max_requests: Maximum requests allowed in the interval (default: 30)
            interval: Time interval in minutes (default: 5)

        Returns:
            Rate limit status and error message if limited
        """
        rate_limit = await self.skill_store.get_agent_skill_data(
            context.agent_id, self.name, "rate_limit"
        )
        current_time = datetime.now(tz=timezone.utc)

        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit.get("count") is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                return True, "Rate limit exceeded"

            rate_limit["count"] += 1
            await self.skill_store.save_agent_skill_data(
                context.agent_id, self.name, "rate_limit", rate_limit
            )
            return False, None

        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        await self.skill_store.save_agent_skill_data(
            context.agent_id, self.name, "rate_limit", new_rate_limit
        )
        return False, None

    async def validate_chain(self, chain: str | None) -> tuple[bool, str | None]:
        """Validate and normalize chain parameter.

        Args:
            chain: Chain name to validate

        Returns:
            Tuple of (is_valid, normalized_chain_name)
        """
        if chain is None:
            return True, None

        normalized_chain = get_chain_from_alias(chain)
        if normalized_chain is None:
            return False, None

        return True, normalized_chain

    def get_endpoint_url(self, endpoint: str) -> str:
        """Construct full endpoint URL.

        Args:
            endpoint: API endpoint path

        Returns:
            Complete URL for the endpoint
        """
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def format_error_response(self, status_code: int, message: str) -> dict:
        """Format error responses consistently.

        Args:
            status_code: HTTP status code
            message: Error message

        Returns:
            Formatted error response dictionary
        """
        return {
            "error": True,
            "status_code": status_code,
            "message": message,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    def get_current_timestamp(self) -> int:
        """Get current timestamp in UTC.

        Returns:
            Current Unix timestamp
        """
        return int(datetime.now(tz=timezone.utc).timestamp())
