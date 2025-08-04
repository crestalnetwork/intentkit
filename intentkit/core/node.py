import logging
from typing import Any, Sequence

from langchain_core.language_models import LanguageModelLike
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import get_runtime
from langgraph.utils.runnable import RunnableCallable
from langmem.short_term.summarization import (
    DEFAULT_EXISTING_SUMMARY_PROMPT,
    DEFAULT_FINAL_SUMMARY_PROMPT,
    DEFAULT_INITIAL_SUMMARY_PROMPT,
    SummarizationResult,
    asummarize_messages,
)

from intentkit.abstracts.graph import AgentContext, AgentError, AgentState
from intentkit.core.credit import skill_cost
from intentkit.models.agent import Agent
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.skill import Skill

logger = logging.getLogger(__name__)


def _validate_chat_history(
    messages: Sequence[BaseMessage],
) -> None:
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

    message = "Found AIMessages with tool_calls that do not have a corresponding ToolMessage. "
    f"Here are the first few of those tool calls: {tool_calls_without_results[:3]}"
    raise ValueError(message)


class PreModelNode(RunnableCallable):
    """LangGraph node that run before the LLM is called."""

    def __init__(
        self,
        *,
        model: LanguageModelLike,
        short_term_memory_strategy: str,
        max_tokens: int,
        max_summary_tokens: int = 1024,
    ) -> None:
        super().__init__(self._func, self._afunc, name="pre_model_node", trace=False)
        self.model = model
        self.short_term_memory_strategy = short_term_memory_strategy
        self.max_tokens = max_tokens
        self.max_tokens_before_summary = max_tokens
        self.max_summary_tokens = max_summary_tokens
        self.token_counter = count_tokens_approximately
        self.initial_summary_prompt = DEFAULT_INITIAL_SUMMARY_PROMPT
        self.existing_summary_prompt = DEFAULT_EXISTING_SUMMARY_PROMPT
        self.final_prompt = DEFAULT_FINAL_SUMMARY_PROMPT
        self.func_accepts_config = True

    def _parse_input(
        self, input: AgentState
    ) -> tuple[list[AnyMessage], dict[str, Any]]:
        messages = input.get("messages")
        context = input.get("context", {})
        if messages is None or not isinstance(messages, list) or len(messages) == 0:
            raise ValueError("Missing required field `messages` in the input.")
        return messages, context

    # overwrite old messages if summarization is used
    def _prepare_state_update(
        self, context: dict[str, Any], summarization_result: SummarizationResult
    ) -> dict[str, Any]:
        state_update = {
            "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]
            + summarization_result.messages
        }
        if summarization_result.running_summary:
            state_update["context"] = {
                **context,
                "running_summary": summarization_result.running_summary,
            }
        return state_update

    def _func(self, AgentState) -> dict[str, Any]:
        raise NotImplementedError("Not implemented yet")

    async def _afunc(self, input: AgentState) -> dict[str, Any]:
        messages, context = self._parse_input(input)
        try:
            _validate_chat_history(messages)
        except ValueError as e:
            logger.error(f"Invalid chat history: {e}")
            logger.info(input)
            # delete all messages
            return {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]}
        if self.short_term_memory_strategy == "trim":
            trimmed_messages = trim_messages(
                messages,
                strategy="last",
                token_counter=self.token_counter,
                max_tokens=self.max_summary_tokens,
                start_on="human",
                end_on=("human", "tool"),
            )
            if len(trimmed_messages) < len(messages):
                logger.info(
                    f"Trimmed messages: {len(messages)} -> {len(trimmed_messages)}"
                )
                if len(trimmed_messages) <= 3:
                    logger.info(f"Too few messages after trim: {len(trimmed_messages)}")
                    return {}
                return {
                    "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)] + trimmed_messages,
                }
            else:
                return {}
        if self.short_term_memory_strategy == "summarize":
            # if last message is not human message, skip summarize
            if not isinstance(messages[-1], HumanMessage):
                return {}
            # summarization is from outside, sometimes it is not stable, so we need to try-catch it
            try:
                summarization_result = await asummarize_messages(
                    messages,
                    running_summary=context.get("running_summary"),
                    model=self.model,
                    max_tokens=self.max_tokens,
                    max_tokens_before_summary=self.max_tokens_before_summary,
                    max_summary_tokens=self.max_summary_tokens,
                    token_counter=self.token_counter,
                    initial_summary_prompt=self.initial_summary_prompt,
                    existing_summary_prompt=self.existing_summary_prompt,
                    final_prompt=self.final_prompt,
                )
                if summarization_result.running_summary:
                    logger.debug(f"Summarization result: {summarization_result}")
                else:
                    logger.debug("Summarization not run")
                return self._prepare_state_update(context, summarization_result)
            except ValueError as e:
                logger.error(f"Invalid chat history: {e}")
                logger.info(input)
                # delete all messages
                return {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]}
        raise ValueError(
            f"Invalid short_term_memory_strategy: {self.short_term_memory_strategy}"
        )


class PostModelNode(RunnableCallable):
    def __init__(self) -> None:
        super().__init__(self._func, self._afunc, name="post_model_node", trace=False)
        self.func_accepts_config = True

    def _func(self, input: AgentState) -> dict[str, Any]:
        raise NotImplementedError("Not implemented yet")

    async def _afunc(self, input: AgentState) -> dict[str, Any]:
        runtime = get_runtime(AgentContext)
        context = runtime.context
        logger.debug(f"Running PostModelNode, input: {input}, context: {context}")
        state_update = {}
        messages = input.get("messages")
        if messages is None or not isinstance(messages, list) or len(messages) == 0:
            raise ValueError("Missing required field `messages` in the input.")
        payer = context.payer
        if not payer:
            return state_update
        logger.debug(f"last: {messages[-1]}")
        msg = messages[-1]
        agent_id = context.agent_id
        agent = await Agent.get(agent_id)
        account = await CreditAccount.get_or_create(OwnerType.USER, payer)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                skill_meta = await Skill.get(tool_call.get("name"))
                if skill_meta:
                    skill_cost_info = await skill_cost(skill_meta.name, payer, agent)
                    total_paid = skill_cost_info.total_amount
                    if not account.has_sufficient_credits(total_paid):
                        state_update["error"] = AgentError.INSUFFICIENT_CREDITS
                        state_update["messages"] = [RemoveMessage(id=msg.id)]
                        state_update["messages"].append(
                            AIMessage(
                                content=f"Insufficient credits. Please top up your account. You need {total_paid} credits, but you only have {account.balance} credits.",
                            )
                        )
                        return state_update
        return state_update


post_model_node = PostModelNode()
