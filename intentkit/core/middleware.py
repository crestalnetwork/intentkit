from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.prompt import build_system_prompt
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.llm import LLMModel, LLMProvider

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
            if model_info.provider == LLMProvider.OPENAI:
                tools.append({"type": "web_search"})
            elif model_info.provider == LLMProvider.XAI:
                tools.extend([{"type": "web_search"}, {"type": "x_search"}])
            elif model_info.provider == LLMProvider.OPENROUTER:
                llm_params["plugins"] = [{"id": "web"}]
            elif model_info.provider == LLMProvider.GOOGLE:
                tools.extend([{"google_search": {}}, {"url_context": {}}])

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
]
