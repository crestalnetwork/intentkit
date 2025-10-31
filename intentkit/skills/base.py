import logging
from collections.abc import Callable, Sequence
from typing import (
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

from coinbase_agentkit import (
    Action,
    AgentKit,
    AgentKitConfig,
    CdpEvmWalletProvider,
)
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.tools.base import ToolException
from langgraph.runtime import get_runtime
from pydantic import (
    ValidationError,
)
from pydantic.v1 import ValidationError as ValidationErrorV1
from redis.exceptions import RedisError

from intentkit.abstracts.graph import AgentContext
from intentkit.clients import get_wallet_provider
from intentkit.models.agent import Agent
from intentkit.models.redis import get_redis
from intentkit.models.skill import (
    AgentSkillData,
    AgentSkillDataCreate,
    ChatSkillData,
    ChatSkillDataCreate,
)
from intentkit.utils.error import IntentKitAPIError, RateLimitExceeded

SkillState = Literal["disabled", "public", "private"]
SkillOwnerState = Literal["disabled", "private"]
APIKeyProviderValue = Literal["platform", "agent_owner"]


class SkillConfig(TypedDict):
    """Abstract base class for skill configuration."""

    enabled: bool
    states: dict[str, SkillState | SkillOwnerState]
    api_key_provider: NotRequired[APIKeyProviderValue]
    __extra__: NotRequired[dict[str, Any]]


class IntentKitSkill(BaseTool):
    """Abstract base class for IntentKit skills.
    Will have predefined abilities.
    """

    # overwrite the value of BaseTool
    handle_tool_error: bool | str | Callable[[ToolException], str] | None = (
        lambda e: f"tool error: {e}"
    )
    """Handle the content of the ToolException thrown."""

    # overwrite the value of BaseTool
    handle_validation_error: (
        bool | str | Callable[[ValidationError | ValidationErrorV1], str] | None
    ) = lambda e: f"validation error: {e}"
    """Handle the content of the ValidationError thrown."""

    # Logger for the class
    logger: logging.Logger = logging.getLogger(__name__)

    @property
    def category(self) -> str:
        """Get the category of the skill."""
        raise NotImplementedError

    async def user_rate_limit(self, limit: int, seconds: int, key: str) -> None:
        """Check if a user has exceeded the rate limit for this skill.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds
            key: The key to use for rate limiting (e.g., skill name or category)

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit

        Returns:
            None: Always returns None if no exception is raised
        """
        try:
            context = self.get_context()
        except ValueError:
            self.logger.info(
                "AgentContext not available, skipping rate limit for %s",
                key,
            )
            return None

        user_identifier = context.user_id or context.agent_id
        if not user_identifier:
            return None  # No rate limiting when no identifier is available

        try:
            max_requests = int(limit)
            window_seconds = int(seconds)
        except (TypeError, ValueError):
            self.logger.info(
                "Invalid user rate limit parameters for %s: limit=%r, seconds=%r",
                key,
                limit,
                seconds,
            )
            return None

        if window_seconds <= 0 or max_requests <= 0:
            return None

        try:
            redis = get_redis()
            # Create a unique key for this rate limit and user
            rate_limit_key = f"rate_limit:{key}:{user_identifier}"

            # Get the current count
            count = await redis.incr(rate_limit_key)

            # Set expiration if this is the first request
            if count == 1:
                await redis.expire(rate_limit_key, window_seconds)

            # Check if user has exceeded the limit
            if count > max_requests:
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

    async def user_rate_limit_by_skill(self, limit: int, seconds: int) -> None:
        """Check if a user has exceeded the rate limit for this specific skill.

        This uses the skill name as the rate limit key.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit
        """
        return await self.user_rate_limit(limit, seconds, self.name)

    async def user_rate_limit_by_category(self, limit: int, seconds: int) -> None:
        """Check if a user has exceeded the rate limit for this skill category.

        This uses the skill category as the rate limit key, which means the limit
        is shared across all skills in the same category.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit
        """
        return await self.user_rate_limit(limit, seconds, self.category)

    async def global_rate_limit(self, limit: int, seconds: int, key: str) -> None:
        """Check if a global rate limit has been exceeded for a given key.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds
            key: The key to use for rate limiting (e.g., skill name or category)

        Raises:
            RateLimitExceeded: If the global limit has been exceeded

        Returns:
            None: Always returns None if no exception is raised
        """
        try:
            max_requests = int(limit)
            window_seconds = int(seconds)
        except (TypeError, ValueError):
            self.logger.info(
                "Invalid global rate limit parameters for %s: limit=%r, seconds=%r",
                key,
                limit,
                seconds,
            )
            return None

        if window_seconds <= 0 or max_requests <= 0:
            return None

        try:
            redis = get_redis()
            rate_limit_key = f"rate_limit:{key}"

            count = await redis.incr(rate_limit_key)

            if count == 1:
                await redis.expire(rate_limit_key, window_seconds)

            if count > max_requests:
                raise RateLimitExceeded(f"Global rate limit exceeded for {key}")

            return None

        except RuntimeError:
            self.logger.info(
                "Redis not initialized, skipping global rate limit for %s",
                key,
            )
            return None
        except RedisError as e:
            self.logger.info(
                f"Redis error in global rate limiting: {e}, skipping rate limit for {key}"
            )
            return None

    async def global_rate_limit_by_skill(self, limit: int, seconds: int) -> None:
        """Apply a global rate limit scoped to this specific skill."""
        return await self.global_rate_limit(limit, seconds, self.name)

    async def global_rate_limit_by_category(self, limit: int, seconds: int) -> None:
        """Apply a global rate limit scoped to this skill category."""
        return await self.global_rate_limit(limit, seconds, self.category)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports synchronous skill calls"
        )

    @staticmethod
    def get_context() -> AgentContext:
        runtime = get_runtime(AgentContext)
        if runtime.context is None or not isinstance(runtime.context, AgentContext):
            raise ValueError("No AgentContext found")
        return runtime.context

    async def get_agent_skill_data(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for this skill scoped to the active agent."""
        return await self.get_agent_skill_data_raw(self.name, key)

    async def get_agent_skill_data_raw(
        self,
        skill_name: str,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for a specific skill scoped to the active agent."""
        context = self.get_context()
        return await AgentSkillData.get(context.agent_id, skill_name, key)

    async def save_agent_skill_data(self, key: str, data: dict[str, Any]) -> None:
        """Persist data for this skill scoped to the active agent."""
        await self.save_agent_skill_data_raw(self.name, key, data)

    async def save_agent_skill_data_raw(
        self,
        skill_name: str,
        key: str,
        data: dict[str, Any],
    ) -> None:
        """Persist data for a specific skill scoped to the active agent."""
        context = self.get_context()
        skill_data = AgentSkillDataCreate(
            agent_id=context.agent_id,
            skill=skill_name,
            key=key,
            data=data,
        )
        await skill_data.save()

    async def delete_agent_skill_data(self, key: str) -> None:
        """Remove persisted data for this skill scoped to the active agent."""
        context = self.get_context()
        await AgentSkillData.delete(context.agent_id, self.name, key)

    async def get_thread_skill_data(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for this skill scoped to the active chat."""
        context = self.get_context()
        return await ChatSkillData.get(context.chat_id, self.name, key)

    async def save_thread_skill_data(self, key: str, data: dict[str, Any]) -> None:
        """Persist data for this skill scoped to the active chat."""
        context = self.get_context()
        skill_data = ChatSkillDataCreate(
            chat_id=context.chat_id,
            agent_id=context.agent_id,
            skill=self.name,
            key=key,
            data=data,
        )
        await skill_data.save()


async def get_agentkit_actions(
    agent_id: str,
    provider_factories: Sequence[Callable[[], object]],
    *,
    agent: Agent | None = None,
) -> list[Action]:
    """Build an AgentKit instance and return its actions."""

    if agent is None:
        try:
            context = IntentKitSkill.get_context()
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise IntentKitAPIError(
                500,
                "AgentContextMissing",
                "Agent context is required to initialize AgentKit actions.",
            ) from exc
        agent = context.agent

    if agent.id != agent_id:
        raise IntentKitAPIError(
            400,
            "AgentMismatch",
            "The requested agent does not match the active context agent.",
        )

    wallet_provider: CdpEvmWalletProvider = await get_wallet_provider(agent)

    agent_kit = AgentKit(
        AgentKitConfig(
            wallet_provider=wallet_provider,
            action_providers=[factory() for factory in provider_factories],
        )
    )
    return agent_kit.get_actions()


def action_to_structured_tool(action: Action) -> StructuredTool:
    """Convert an AgentKit action to a LangChain StructuredTool."""

    def _tool_fn(**kwargs: object) -> str:
        return action.invoke(kwargs)

    tool = StructuredTool(
        name=action.name,
        description=action.description,
        func=_tool_fn,
        args_schema=action.args_schema,
    )
    tool.handle_tool_error = lambda e: f"tool error: {e}"
    tool.handle_validation_error = lambda e: f"validation error: {e}"
    return tool
