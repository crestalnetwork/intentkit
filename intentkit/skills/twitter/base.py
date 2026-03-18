from langchain_core.tools.base import ToolException

from intentkit.skills.base import IntentKitSkill


class TwitterBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    def get_api_key(self):
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
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
                raise ToolException(f"Missing required {key} in configuration")
        return api_keys

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
