from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class TwitterBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    def get_api_key(self):
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

    category: str = "twitter"

    async def check_rate_limit(self, max_requests: int = 1, interval: int = 15) -> None:
        """Check if the rate limit has been exceeded.

        Delegates to global_rate_limit with Redis atomic INCR for concurrency safety.

        Args:
            max_requests: Maximum number of requests allowed within the rate limit window.
            interval: Time interval in minutes for the rate limit window.

        Raises:
            RateLimitExceeded: If the rate limit has been exceeded.
        """
        context = self.get_context()
        agent_id = context.agent_id
        key = f"twitter_rate_limit:{agent_id}:{self.name}"
        await self.global_rate_limit(max_requests, interval * 60, key)
