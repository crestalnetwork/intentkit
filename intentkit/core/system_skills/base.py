"""Base class for IntentKit system skills."""

import logging
from abc import ABCMeta
from collections.abc import Callable
from typing import Any, cast, override

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException
from langgraph.runtime import get_runtime
from pydantic import ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from intentkit.abstracts.graph import AgentContext


class SystemSkill(BaseTool, metaclass=ABCMeta):
    """Abstract base class for IntentKit system skills.

    System skills are built-in skills available to all agents without
    additional configuration. This base class provides consistent error
    handling so that tool exceptions are returned as messages to the LLM
    instead of crashing the agent.
    """

    # Ensure ToolException is caught and returned as a message to the LLM
    handle_tool_error: bool | str | Callable[[ToolException], str] | None = lambda e: (
        f"tool error: {e}"
    )
    """Handle the content of the ToolException thrown."""

    # Ensure ValidationError is caught and returned as a message to the LLM
    handle_validation_error: (
        bool | str | Callable[[ValidationError | ValidationErrorV1], str] | None
    ) = lambda e: f"validation error: {e}"
    """Handle the content of the ValidationError thrown."""

    logger: logging.Logger = logging.getLogger(__name__)

    @override
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports asynchronous skill calls"
        )

    @staticmethod
    def get_context() -> AgentContext:
        """Retrieve the current AgentContext from the LangGraph runtime."""
        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ValueError("No AgentContext found")
        return context
