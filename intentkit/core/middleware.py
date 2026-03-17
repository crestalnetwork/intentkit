from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.tools import BaseTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.prompt import build_system_prompt
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.llm import LLMModel, LLMProvider

logger = logging.getLogger(__name__)


def _validate_chat_history(messages: Sequence[BaseMessage]) -> None:
    """Validate that all tool calls in AIMessages have a corresponding ToolMessage."""

    all_tool_calls = [
        tool_call
        for message in messages
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
    ]
    tool_call_ids_with_results = {
        message.tool_call_id for message in messages if isinstance(message, ToolMessage)
    }
    tool_calls_without_results = [
        tool_call
        for tool_call in all_tool_calls
        if tool_call["id"] not in tool_call_ids_with_results
    ]
    if not tool_calls_without_results:
        return

    message = (
        "Found AIMessages with tool_calls that do not have a corresponding ToolMessage. "
        f"Here are the first few of those tool calls: {tool_calls_without_results[:3]}"
    )
    raise ValueError(message)


class TrimMessagesMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that trims conversation history before invoking the model."""

    max_summary_tokens: int

    def __init__(self, *, max_summary_tokens: int) -> None:
        super().__init__()
        self.max_summary_tokens = max_summary_tokens

    @override
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any]:
        del runtime
        messages = state.get("messages")
        context = state.get("context", {})
        if not messages:
            raise ValueError("Missing required field `messages` in the input.")
        try:
            _validate_chat_history(messages)
        except ValueError as e:
            logger.error("Invalid chat history: %s", e)
            logger.info(state)
            return {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]}

        trimmed_messages = trim_messages(
            messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=self.max_summary_tokens,
            start_on="human",
            end_on=("human", "tool"),
        )
        if len(trimmed_messages) < len(messages):
            logger.info(
                "Trimmed messages: %s -> %s", len(messages), len(trimmed_messages)
            )
            if len(trimmed_messages) <= 3:
                logger.info("Too few messages after trim: %s", len(trimmed_messages))
                return {}
            return {
                "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)] + trimmed_messages,
                "context": context,
            }
        return {}


class DynamicPromptMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that builds the system prompt dynamically per request."""

    agent: Agent
    agent_data: AgentData

    def __init__(self, agent: Agent, agent_data: AgentData) -> None:
        super().__init__()
        self.agent = agent
        self.agent_data = agent_data

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context: AgentContext = request.runtime.context
        system_prompt = await build_system_prompt(self.agent, self.agent_data, context)
        updated_request = request.override(system_prompt=system_prompt)  # pyright: ignore[reportCallIssue]
        return await handler(updated_request)


class ToolBindingMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that selects tools and model parameters based on context."""

    llm_model: LLMModel
    public_tools: list[BaseTool | dict[str, Any]]
    private_tools: list[BaseTool | dict[str, Any]]

    def __init__(
        self,
        llm_model: LLMModel,
        public_tools: list[BaseTool | dict[str, Any]],
        private_tools: list[BaseTool | dict[str, Any]],
    ) -> None:
        super().__init__()
        self.llm_model = llm_model
        self.public_tools = public_tools
        self.private_tools = private_tools

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context: AgentContext = request.runtime.context

        llm_params: dict[str, Any] = {}
        # Tools are already deduplicated at build time in executor.py
        tools: list[BaseTool | dict[str, Any]] = list(
            self.private_tools if context.is_private else self.public_tools
        )

        if context.agent.search_internet:
            model_info = await self.llm_model.model_info()
            if model_info.supports_search:
                if model_info.provider == LLMProvider.OPENAI:
                    tools.append({"type": "web_search"})
                elif model_info.provider == LLMProvider.XAI:
                    tools.extend([{"type": "web_search"}, {"type": "x_search"}])
                elif model_info.provider == LLMProvider.OPENROUTER:
                    llm_params["plugins"] = [{"id": "web"}]
                elif model_info.provider == LLMProvider.GOOGLE:
                    tools.extend([{"google_search": {}}, {"url_context": {}}])
            else:
                logger.debug(
                    "Search requested but model does not support native search"
                )

        model = await self.llm_model.create_instance(llm_params)
        updated_request = request.override(
            model=model,
            tools=tools,
            model_settings=llm_params,
        )
        return await handler(updated_request)


class StepTrackingMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that tracks the number of steps in the agent execution."""

    @override
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any]:
        del runtime
        step_count = state.get("step_count", 0)
        step_count += 1
        logger.debug("Step tracking: %s", step_count)
        return {"step_count": step_count}


__all__ = [
    "DynamicPromptMiddleware",
    "StepTrackingMiddleware",
    "SummarizationMiddleware",
    "ToolBindingMiddleware",
    "TrimMessagesMiddleware",
]
