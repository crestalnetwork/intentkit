from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.prompt import build_system_prompt
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.llm import LLMModel

logger = logging.getLogger(__name__)


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
    extra_llm_params: dict[str, Any]

    def __init__(
        self,
        llm_model: LLMModel,
        public_tools: list[BaseTool | dict[str, Any]],
        private_tools: list[BaseTool | dict[str, Any]],
        extra_llm_params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.llm_model = llm_model
        self.public_tools = public_tools
        self.private_tools = private_tools
        self.extra_llm_params = extra_llm_params or {}

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context: AgentContext = request.runtime.context

        llm_params: dict[str, Any] = {**self.extra_llm_params}
        # Tools are already deduplicated at build time in executor.py
        tools: list[BaseTool | dict[str, Any]] = list(
            self.private_tools if context.is_private else self.public_tools
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


class EmptyContentSafetyMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Sanitize AIMessages with empty list content to prevent Gemini 3 API errors.

    Gemini 3 stores empty content as [] (list) instead of "" (string).
    If tool_calls are lost from such a message (e.g. during checkpoint
    serialization), converting content=[] produces Content(parts=[]) which
    the Gemini API rejects with "must include at least one parts field".

    This middleware patches any such message before the model call.
    """

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        messages = request.messages
        patched = False
        for i, msg in enumerate(messages):
            if (
                isinstance(msg, AIMessage)
                and isinstance(msg.content, list)
                and len(msg.content) == 0
                and not msg.tool_calls
            ):
                messages[i] = msg.model_copy(update={"content": ""})
                patched = True
                logger.warning(
                    "Patched AIMessage with empty content[] at index %d "
                    "(no tool_calls) — would have caused Gemini empty-parts error",
                    i,
                )
        if patched:
            request = request.override(messages=messages)
        return await handler(request)


__all__ = [
    "DynamicPromptMiddleware",
    "EmptyContentSafetyMiddleware",
    "StepTrackingMiddleware",
    "SummarizationMiddleware",
    "ToolBindingMiddleware",
]
