from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, cast, override

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
from langgraph.types import StreamWriter

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

from intentkit.abstracts.graph import AgentContext, AgentError, AgentState
from intentkit.core.credit import skill_cost
from intentkit.core.prompt import build_system_prompt
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.llm import LLMModel, LLMProvider
from intentkit.models.skill import Skill

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
            logger.error(f"Invalid chat history: {e}")
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
            logger.info(f"Trimmed messages: {len(messages)} -> {len(trimmed_messages)}")
            if len(trimmed_messages) <= 3:
                logger.info(f"Too few messages after trim: {len(trimmed_messages)}")
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
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context = cast(AgentContext, request.runtime.context)
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
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context = cast(AgentContext, request.runtime.context)

        llm_params: dict[str, Any] = {}
        tools: list[BaseTool | dict[str, Any]] = (
            self.private_tools if context.is_private else self.public_tools
        )
        tools = list(
            {
                tool.name if isinstance(tool, BaseTool) else str(tool): tool
                for tool in tools
            }.values()
        )

        if context.search or context.agent.has_search():
            if self.llm_model.info.supports_search:
                tools.append({"type": "web_search"})
                if (
                    self.llm_model.info.provider == LLMProvider.OPENAI
                    and self.llm_model.model_name == "gpt-5-mini"
                ):
                    llm_params["reasoning_effort"] = "medium"
                if self.llm_model.info.provider == LLMProvider.XAI:
                    llm_params["search_parameters"] = {"mode": "auto"}
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


class CreditCheckMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that validates tool affordability before execution."""

    func_accepts_config: bool

    def __init__(self) -> None:
        super().__init__()
        self.func_accepts_config = True

    @override
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime[AgentContext],
        *,
        writer: StreamWriter | None = None,
    ) -> dict[str, Any]:
        context = runtime.context
        messages = state.get("messages")
        if not messages or len(messages) == 0:
            raise ValueError("Missing required field `messages` in the input.")

        payer = context.payer
        if not payer:
            return {}

        msg = messages[-1]
        agent = context.agent
        account = await CreditAccount.get_or_create(OwnerType.USER, payer)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                skill_meta = await Skill.get(tool_call["name"])
                if not skill_meta:
                    continue
                skill_cost_info = await skill_cost(skill_meta.name, payer, agent)
                total_paid = skill_cost_info.total_amount
                if not account.has_sufficient_credits(total_paid):
                    error_message = (
                        "Insufficient credits. Please top up your account. "
                        f"You need {total_paid} credits, but you only have {account.balance} credits."
                    )
                    msg_id = msg.id if msg.id else ""
                    state_update: dict[str, Any] = {
                        "error": AgentError.INSUFFICIENT_CREDITS,
                        "messages": [
                            RemoveMessage(id=msg_id),
                            AIMessage(content=error_message),
                        ],
                    }
                    if writer:
                        writer(
                            {
                                "credit_check": {
                                    "error": AgentError.INSUFFICIENT_CREDITS,
                                    "message": error_message,
                                }
                            }
                        )
                    return state_update
        return {}


__all__ = [
    "CreditCheckMiddleware",
    "DynamicPromptMiddleware",
    "SummarizationMiddleware",
    "ToolBindingMiddleware",
    "TrimMessagesMiddleware",
]
