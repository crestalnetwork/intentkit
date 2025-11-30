from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.error import RateLimitExceeded


class TwitterBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    def get_api_key(self) -> dict[str, Any]:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            # Return platform keys (these need to be added to config.py)
            platform_keys = {
                "consumer_key": getattr(config, "twitter_consumer_key", None),
                "consumer_secret": getattr(config, "twitter_consumer_secret", None),
                "access_token": getattr(config, "twitter_access_token", None),
                "access_token_secret": getattr(
                    config, "twitter_access_token_secret", None
                ),
            }
            missing = [key for key, value in platform_keys.items() if not value]
            if missing:
                raise ToolException(
                    "Twitter platform API keys are not configured: "
                    + ", ".join(missing)
                )
            return platform_keys
        # for backward compatibility or agent_owner provider
        elif api_key_provider == "agent_owner":
            required_keys = [
                "consumer_key",
                "consumer_secret",
                "access_token",
                "access_token_secret",
            ]
            api_keys = {}
            for key in required_keys:
                if skill_config.get(key):
                    api_keys[key] = skill_config.get(key)
                else:
                    raise ToolException(
                        f"Missing required {key} in agent_owner configuration"
                    )
            return api_keys
        else:
            raise ToolException(f"Invalid API key provider: {api_key_provider}")

    @property
    def category(self) -> str:
        return "twitter"

    async def check_rate_limit(self, max_requests: int = 1, interval: int = 15) -> None:
        """Check if the rate limit has been exceeded.

        Args:
            max_requests: Maximum number of requests allowed within the rate limit window.
            interval: Time interval in minutes for the rate limit window.

        Raises:
            RateLimitExceeded: If the rate limit has been exceeded.
        """
        rate_limit = await self.get_agent_skill_data("rate_limit")

        current_time = datetime.now(tz=UTC)

        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit["count"] is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                raise RateLimitExceeded("Rate limit exceeded")

            rate_limit["count"] += 1
            await self.save_agent_skill_data("rate_limit", rate_limit)

            return

        # If no rate limit exists or it has expired, create a new one
        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        await self.save_agent_skill_data("rate_limit", new_rate_limit)
        return
