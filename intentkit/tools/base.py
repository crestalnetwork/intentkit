"""Base classes and utilities for IntentKit tools."""

import logging
from abc import ABCMeta
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import (
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException, ToolExceptionHandlerOutput
from langgraph.runtime import get_runtime
from pydantic import (
    BaseModel,
    ValidationError,
)
from pydantic.v1 import ValidationError as ValidationErrorV1

from intentkit.abstracts.graph import AgentContext
from intentkit.config.redis import get_redis
from intentkit.models.tool import (
    AgentToolData,
    AgentToolDataCreate,
    ChatToolData,
    ChatToolDataCreate,
)
from intentkit.utils.error import RateLimitExceeded

ToolState = Literal["disabled", "public", "private"]
ToolOwnerState = Literal["disabled", "private"]


class NoArgsSchema(BaseModel):
    """Empty schema for tools without arguments."""


class ToolsetConfig(TypedDict):
    """Abstract base class for tool configuration."""

    enabled: bool
    states: Any
    __extra__: NotRequired[dict[str, Any]]


def is_tool_visible(state: object, is_private: bool) -> bool:
    """Whether a tool/toolset with this visibility state is exposed here.

    "public" is always visible; "private" only to the agent owner/team;
    "disabled" (or anything unset) never.
    """
    return state == "public" or (state == "private" and is_private)


def filter_enabled_tool_names(
    states: Mapping[str, object], is_private: bool
) -> list[str]:
    """Tool names whose configured state allows them in this context."""
    return [
        name for name, state in states.items() if is_tool_visible(state, is_private)
    ]


class IntentKitTool(BaseTool, metaclass=ABCMeta):
    """Abstract base class for IntentKit tools.
    Will have predefined abilities.
    """

    # overwrite the value of BaseTool
    handle_tool_error: (
        bool | str | Callable[[ToolException], ToolExceptionHandlerOutput] | None
    ) = lambda e: f"tool error: {e}"
    """Handle the content of the ToolException thrown."""

    # overwrite the value of BaseTool
    handle_validation_error: (
        bool | str | Callable[[ValidationError | ValidationErrorV1], str] | None
    ) = lambda e: f"validation error: {e}"
    """Handle the content of the ValidationError thrown."""

    # Logger for the class
    logger: logging.Logger = logging.getLogger(__name__)

    category: str
    """Get the category of the tool."""

    def available(self) -> bool:
        """Check if this tool is available. Override in subclasses to check dependencies."""
        return True

    price: Decimal = Decimal("1")
    """Price for the tool. Override in subclasses for non-default pricing."""

    async def user_rate_limit(self, limit: int, seconds: int, key: str) -> None:
        """Check if a user has exceeded the rate limit for this tool.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds
            key: The key to use for rate limiting (e.g., tool name or category)

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

    async def user_rate_limit_by_tool(self, limit: int, seconds: int) -> None:
        """Check if a user has exceeded the rate limit for this specific tool.

        This uses the tool name as the rate limit key.

        Args:
            limit: Maximum number of requests allowed
            seconds: Time window in seconds

        Raises:
            RateLimitExceeded: If the user has exceeded the rate limit
        """
        return await self.user_rate_limit(limit, seconds, self.name)

    async def user_rate_limit_by_category(self, limit: int, seconds: int) -> None:
        """Check if a user has exceeded the rate limit for this toolset.

        This uses the toolset as the rate limit key, which means the limit
        is shared across all tools in the same category.

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
            key: The key to use for rate limiting (e.g., tool name or category)

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

        redis = get_redis()
        rate_limit_key = f"rate_limit:{key}"

        count = await redis.incr(rate_limit_key)

        if count == 1:
            await redis.expire(rate_limit_key, window_seconds)

        if count > max_requests:
            raise RateLimitExceeded(f"Global rate limit exceeded for {key}")

        return None

    async def global_rate_limit_by_tool(self, limit: int, seconds: int) -> None:
        """Apply a global rate limit scoped to this specific tool."""
        return await self.global_rate_limit(limit, seconds, self.name)

    async def global_rate_limit_by_category(self, limit: int, seconds: int) -> None:
        """Apply a global rate limit scoped to this toolset."""
        return await self.global_rate_limit(limit, seconds, self.category)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports synchronous tool calls"
        )

    @staticmethod
    def get_context() -> AgentContext:
        runtime = get_runtime(AgentContext)
        if runtime.context is None or not isinstance(runtime.context, AgentContext):
            raise ValueError("No AgentContext found")
        return runtime.context

    async def get_agent_tool_data(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for this tool scoped to the active agent."""
        return await self.get_agent_tool_data_raw(self.name, key)

    async def get_agent_tool_data_raw(
        self,
        tool_name: str,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for a specific tool scoped to the active agent."""
        context = self.get_context()
        return await AgentToolData.get(context.agent_id, tool_name, key)

    async def save_agent_tool_data(self, key: str, data: dict[str, Any]) -> None:
        """Persist data for this tool scoped to the active agent."""
        await self.save_agent_tool_data_raw(self.name, key, data)

    async def save_agent_tool_data_raw(
        self,
        tool_name: str,
        key: str,
        data: dict[str, Any],
    ) -> None:
        """Persist data for a specific tool scoped to the active agent."""
        context = self.get_context()
        tool_data = AgentToolDataCreate(
            agent_id=context.agent_id,
            tool=tool_name,
            key=key,
            data=data,
        )
        await tool_data.save()

    async def delete_agent_tool_data(self, key: str) -> None:
        """Remove persisted data for this tool scoped to the active agent."""
        context = self.get_context()
        await AgentToolData.delete(context.agent_id, self.name, key)

    async def get_thread_tool_data(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve persisted data for this tool scoped to the active chat."""
        context = self.get_context()
        return await ChatToolData.get(context.chat_id, self.name, key)

    async def save_thread_tool_data(self, key: str, data: dict[str, Any]) -> None:
        """Persist data for this tool scoped to the active chat."""
        context = self.get_context()
        tool_data = ChatToolDataCreate(
            chat_id=context.chat_id,
            agent_id=context.agent_id,
            tool=self.name,
            key=key,
            data=data,
        )
        await tool_data.save()


# Global tool price registry
_DEFAULT_PRICE = Decimal("1")
_TOOL_PRICES: dict[str, Decimal] = {}
_registry_built = False


def _collect_subclasses(cls: type) -> list[type]:
    """Recursively collect all subclasses."""
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_collect_subclasses(sub))
    return result


def build_tool_prices() -> None:
    """Scan all tool modules and collect {name: price} from IntentKitTool subclasses."""
    global _registry_built
    if _registry_built:
        return

    import importlib
    import pkgutil
    from pathlib import Path

    tools_dir = Path(__file__).parent
    # Import all tool sub-packages to trigger class registration
    for module_info in pkgutil.walk_packages(
        [str(tools_dir)], prefix="intentkit.tools."
    ):
        try:
            importlib.import_module(module_info.name)
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to import tool module %s", module_info.name, exc_info=True
            )

    from pydantic_core import PydanticUndefined

    # Pydantic v2 stores field defaults in model_fields[...].default, not as class attributes.
    for cls in _collect_subclasses(IntentKitTool):
        name = cls.model_fields["name"].default
        # Skip abstract classes without a concrete name default (isinstance excludes PydanticUndefined)
        if not isinstance(name, str) or not name:
            continue
        price = cls.model_fields["price"].default
        if isinstance(price, Decimal):
            _TOOL_PRICES[name] = price
        elif price is PydanticUndefined:
            _TOOL_PRICES[name] = _DEFAULT_PRICE
        else:
            _TOOL_PRICES[name] = Decimal(str(price))

    _registry_built = True


def get_tool_price(name: str) -> Decimal:
    """Get price for a tool by name. Returns the default price if not found."""
    if not _registry_built:
        build_tool_prices()
    return _TOOL_PRICES.get(name, _DEFAULT_PRICE)
