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

    team_only: bool = False
    """Tools that act with the agent's identity or assets (publishing,
    spending) are only bound when the owning team runs the agent; guests of
    a published agent never see them. Runtime code must still call
    ``ensure_own_team()`` as a second line of defense."""

    interactive_only: bool = False
    """Tools that render interactive UI components (cards, choice buttons)
    need a live user watching the conversation. ToolBindingMiddleware drops
    them for cron-triggered runs (entrypoint TRIGGER) and sub-agent calls,
    where nobody can see or click the component."""

    requires_memory_scope: bool = False
    """Tools that read/write the conversation's scoped memories only work
    when the conversation resolves at least one memory scope.
    ToolBindingMiddleware drops them from sub-agent runs (stateless by
    design) and teamless anonymous conversations, where every call would
    fail."""

    main_agent_only: bool = False
    """Tools that manage the entry conversation's own working state (the
    todo list) make no sense inside a sub-agent run — a sub-agent is a
    one-shot worker whose plan belongs to the calling agent.
    ToolBindingMiddleware drops them when ``context.is_subagent``."""

    context_editing_exempt: bool = False
    """Tool results that must survive context editing: ClearToolUsesEdit
    skips them. The ``write_todos`` echo is the model's only view of the
    current todo list between compactions; UI card/choice results carry
    the rendered payload the conversation refers back to."""

    def ensure_own_team(self) -> None:
        """Refuse execution unless the owning team is running the agent."""
        context = self.get_context()
        if not context.is_own_team:
            raise ToolException(
                f"{self.name} is not allowed in this conversation: it acts "
                "with the agent's identity and can only be used by the "
                "agent's own team."
            )

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
