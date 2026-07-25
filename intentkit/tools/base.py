"""Base classes and utilities for IntentKit tools."""

import logging
from abc import ABCMeta
from collections.abc import Callable
from decimal import Decimal
from functools import lru_cache
from typing import Any

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


class NoArgsSchema(BaseModel):
    """Empty schema for tools without arguments."""


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

    @property
    def logger(self) -> logging.Logger:
        """Logger named after the concrete tool's own module.

        This used to be a class attribute, which stamped every tool's records
        with ``intentkit.tools.base``. ``record.name`` is the only per-tool
        identifier the JSON formatter emits (utils/logging.py), so a shared
        logger erased which tool actually logged the line.
        """
        return logging.getLogger(type(self).__module__)

    category: str
    """Get the category of the tool."""

    title: str = ""
    """Human-readable display name for tool pickers; falls back to the name."""

    team_only: bool = False
    """Tools that operate the team's assets (signing/spending) are only
    bound when the owning team runs the agent; guests of a published agent
    never see them. Signing paths must still call ``ensure_signing_allowed``
    as a second line of defense."""

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
_modules_imported = False


def _collect_subclasses(cls: type) -> list[type]:
    """Recursively collect all subclasses."""
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_collect_subclasses(sub))
    return result


def import_all_tool_modules() -> None:
    """Import every module under intentkit.tools to register tool subclasses.

    Broken modules are skipped with a warning so one misconfigured toolset
    never takes down registry construction. Runs the package walk only once
    per process (failed imports are not retried — they would just re-log).
    """
    global _modules_imported
    if _modules_imported:
        return

    import importlib
    import pkgutil
    from pathlib import Path

    tools_dir = Path(__file__).parent
    for module_info in pkgutil.walk_packages(
        [str(tools_dir)], prefix="intentkit.tools."
    ):
        try:
            importlib.import_module(module_info.name)
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to import tool module %s", module_info.name, exc_info=True
            )

    _modules_imported = True


def collect_tool_classes() -> list[type["IntentKitTool"]]:
    """All registered IntentKitTool subclasses (import side effects included)."""
    import_all_tool_modules()
    return _collect_subclasses(IntentKitTool)


@lru_cache(maxsize=1)
def tool_classes_by_name() -> dict[str, type["IntentKitTool"]]:
    """Concrete tool classes keyed by their ``name`` default.

    Abstract bases (no concrete name) are skipped. Treat as read-only.
    """
    classes: dict[str, type[IntentKitTool]] = {}
    for cls in collect_tool_classes():
        cls_name = tool_field_default(cls, "name")
        if isinstance(cls_name, str) and cls_name:
            classes[cls_name] = cls
    return classes


# Lazy singleton instances by tool name, for callers that need an instance
# outside a toolset module's own cache (e.g. per-tool availability checks).
# Tool classes are default-constructible — the eager toolsets build
# import-time instance caches the same way.
_TOOL_INSTANCES: dict[str, "IntentKitTool"] = {}


def get_tool_instance(name: str) -> "IntentKitTool | None":
    """A singleton instance of the named tool, or None if unknown.

    Instantiation failures are logged and reported as None so a broken tool
    never takes down a listing.
    """
    cached = _TOOL_INSTANCES.get(name)
    if cached is not None:
        return cached

    cls = tool_classes_by_name().get(name)
    if cls is None:
        return None
    try:
        # Concrete tool classes declare all fields with defaults; only the
        # abstract bases (never in the name map) have required fields.
        instance = cls()  # pyright: ignore[reportCallIssue]
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to instantiate tool %s", name, exc_info=True
        )
        return None
    _TOOL_INSTANCES[name] = instance
    return instance


def tool_field_default(cls: type, field: str) -> Any:
    """Class-level default of a pydantic field, or None when it has none.

    Pydantic v2 stores field defaults in ``model_fields[...].default`` (with
    the ``PydanticUndefined`` sentinel), not as class attributes; abstract
    tool bases have no concrete ``name`` default and yield None here.
    """
    from pydantic_core import PydanticUndefined

    model_field = getattr(cls, "model_fields", {}).get(field)
    if model_field is None or model_field.default is PydanticUndefined:
        return None
    return model_field.default


def build_tool_prices() -> None:
    """Scan all tool modules and collect {name: price} from IntentKitTool subclasses."""
    global _registry_built
    if _registry_built:
        return

    for name, cls in tool_classes_by_name().items():
        price = tool_field_default(cls, "price")
        if isinstance(price, Decimal):
            _TOOL_PRICES[name] = price
        elif price is None:
            _TOOL_PRICES[name] = _DEFAULT_PRICE
        else:
            _TOOL_PRICES[name] = Decimal(str(price))

    _registry_built = True


def get_tool_price(name: str) -> Decimal:
    """Get price for a tool by name. Returns the default price if not found."""
    if not _registry_built:
        build_tool_prices()
    return _TOOL_PRICES.get(name, _DEFAULT_PRICE)
