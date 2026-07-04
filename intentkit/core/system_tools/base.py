"""Base class for IntentKit system tools."""

import logging
from abc import ABCMeta
from collections.abc import Callable
from typing import Any, cast, override

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException, ToolExceptionHandlerOutput
from langgraph.runtime import get_runtime
from pydantic import ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from intentkit.abstracts.graph import AgentContext


class SystemTool(BaseTool, metaclass=ABCMeta):
    """Abstract base class for IntentKit system tools.

    System tools are built-in tools available to all agents without
    additional configuration. This base class provides consistent error
    handling so that tool exceptions are returned as messages to the LLM
    instead of crashing the agent.
    """

    # Ensure ToolException is caught and returned as a message to the LLM
    handle_tool_error: (
        bool | str | Callable[[ToolException], ToolExceptionHandlerOutput] | None
    ) = lambda e: f"tool error: {e}"
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
            "Use _arun instead, IntentKit only supports asynchronous tool calls"
        )

    @staticmethod
    def get_context() -> AgentContext:
        """Retrieve the current AgentContext from the LangGraph runtime."""
        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ValueError("No AgentContext found")
        return context

    async def _bill_internal_llm(
        self, response: Any, tool_call_id: str | None, model_id: str
    ) -> None:
        """Bill the team for an internal LLM call made inside a tool.

        Best-effort: token usage is read from the LangChain ``response`` and
        any billing failure is logged, never raised.
        """
        usage = response.usage_metadata or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_input_tokens = usage.get("input_token_details", {}).get("cache_read", 0)
        try:
            context = self.get_context()
            payer = context.payer
            if payer and tool_call_id:
                from intentkit.core.credit.expense import expense_tool_internal_llm

                await expense_tool_internal_llm(
                    team_id=payer,
                    agent=context.agent,
                    tool_name=self.name,
                    tool_call_id=tool_call_id,
                    start_message_id=context.start_message_id,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                    user_id=context.user_id,
                )
        except Exception as e:
            self.logger.warning(
                "%s: failed to bill internal LLM usage: %s", self.name, e
            )
