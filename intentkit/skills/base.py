import asyncio
import logging
from typing import Any, Callable, Dict, Literal, NotRequired, Optional, TypedDict, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException
from pydantic import (
    BaseModel,
    ValidationError,
)
from pydantic.v1 import ValidationError as ValidationErrorV1
from redis.exceptions import RedisError

from intentkit.abstracts.exception import RateLimitExceeded
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.models.agent import Agent
from intentkit.models.redis import get_redis

SkillState = Literal["disabled", "public", "private"]
SkillOwnerState = Literal["disabled", "private"]


class SkillConfig(TypedDict):
    """Abstract base class for skill configuration."""

    enabled: bool
    states: Dict[str, SkillState | SkillOwnerState]
    api_key_provider: NotRequired[str]
    __extra__: NotRequired[Dict[str, Any]]


class SkillContext(BaseModel):
    skill_category: str
    agent_id: str
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    app_id: Optional[str] = None
    entrypoint: Literal["web", "twitter", "telegram", "trigger", "api"]
    is_private: bool
    payer: Optional[str] = None
    _agent: Optional[Agent] = None

    @property
    def agent(self) -> Agent:
        if self._agent is None:
            self._agent = asyncio.run(Agent.get(self.agent_id))
        return self._agent

    @property
    def config(self) -> Dict[str, Any]:
        agent = self.agent
        config = None
        if agent.skills:
            config = agent.skills.get(self.skill_category)
        if not config:
            raise ValueError(
                f"Skill {self.skill_category} not found in agent {self.agent_id}"
            )
        return config


class IntentKitSkill(BaseTool):
    """Abstract base class for IntentKit skills.
    Will have predefined abilities.
    """

    skill_store: SkillStoreABC
    # overwrite the value of BaseTool
    handle_tool_error: Optional[Union[bool, str, Callable[[ToolException], str]]] = (
        lambda e: f"tool error: {e}"
    )
    """Handle the content of the ToolException thrown."""

    # overwrite the value of BaseTool
    handle_validation_error: Optional[
        Union[bool, str, Callable[[Union[ValidationError, ValidationErrorV1]], str]]
    ] = lambda e: f"validation error: {e}"
    """Handle the content of the ValidationError thrown."""

    # Logger for the class
    logger: logging.Logger = logging.getLogger(__name__)

    @property
    def category(self) -> str:
        """Get the category of the skill."""
        raise NotImplementedError

    async def user_rate_limit(
        self, user_id: str, limit: int, minutes: int, key: str
    ) -> None:
        """Check if a user has exceeded the rate limit for this skill.

        Args:
            user_id: The ID of the user to check
            limit: Maximum number of requests allowed
            minutes: Time window in minutes
            key: The key to use for rate limiting (e.g., skill name or category)

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit

        Returns:
            None: Always returns None if no exception is raised
        """
        if not user_id:
            return None  # No rate limiting for users without ID

        try:
            redis = get_redis()
            # Create a unique key for this rate limit and user
            rate_limit_key = f"rate_limit:{key}:{user_id}"

            # Get the current count
            count = await redis.incr(rate_limit_key)

            # Set expiration if this is the first request
            if count == 1:
                await redis.expire(
                    rate_limit_key, minutes * 60
                )  # Convert minutes to seconds

            # Check if user has exceeded the limit
            if count > limit:
                raise RateLimitExceeded(f"Rate limit exceeded for {key}")

            return None

        except RuntimeError:
            # Redis client not initialized, log and allow the request
            self.logger.info(f"Redis not initialized, skipping rate limit for {key}")
            return None
        except RedisError as e:
            # Redis error, log and allow the request
            self.logger.info(
                f"Redis error in rate limiting: {e}, skipping rate limit for {key}"
            )
            return None

    async def user_rate_limit_by_skill(
        self, user_id: str, limit: int, minutes: int
    ) -> None:
        """Check if a user has exceeded the rate limit for this specific skill.

        This uses the skill name as the rate limit key.

        Args:
            user_id: The ID of the user to check
            limit: Maximum number of requests allowed
            minutes: Time window in minutes

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit
        """
        return await self.user_rate_limit(user_id, limit, minutes, self.name)

    async def user_rate_limit_by_category(
        self, user_id: str, limit: int, minutes: int
    ) -> None:
        """Check if a user has exceeded the rate limit for this skill category.

        This uses the skill category as the rate limit key, which means the limit
        is shared across all skills in the same category.

        Args:
            user_id: The ID of the user to check
            limit: Maximum number of requests allowed
            minutes: Time window in minutes

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit
        """
        return await self.user_rate_limit(user_id, limit, minutes, self.category)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports synchronous skill calls"
        )

    def context_from_config(self, runner_config: RunnableConfig) -> SkillContext:
        if "configurable" not in runner_config:
            raise ValueError("configurable not in runner_config")
        configurable = runner_config["configurable"]
        if not configurable:
            raise ValueError("configurable in runnable config is empty")
        return SkillContext(
            skill_category=self.category,
            agent_id=configurable.get("agent_id"),
            user_id=configurable.get("user_id"),
            app_id=configurable.get("app_id"),
            chat_id=configurable.get("chat_id"),
            entrypoint=configurable.get("entrypoint"),
            is_private=configurable.get("is_private"),
        )
