import logging
from typing import Any

from langchain_core.language_models import LanguageModelLike
from langchain_core.messages import (
    AnyMessage,
    RemoveMessage,
)
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.utils.runnable import RunnableCallable
from langmem.short_term.summarization import (
    DEFAULT_EXISTING_SUMMARY_PROMPT,
    DEFAULT_FINAL_SUMMARY_PROMPT,
    DEFAULT_INITIAL_SUMMARY_PROMPT,
    SummarizationResult,
    asummarize_messages,
)
from pydantic import BaseModel

from abstracts.graph import AgentState

logger = logging.getLogger(__name__)


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
        if messages is None:
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

    async def _afunc(
        self,
        input: AgentState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        # logger.debug(f"Running PreModelNode, input: {input}, config: {config}")
        messages, context = self._parse_input(input)
        if self.short_term_memory_strategy == "trim":
            trimmed_messages = trim_messages(
                messages,
                strategy="last",
                token_counter=self.token_counter,
                max_tokens=self.max_summary_tokens,
                start_on="human",
                end_on=("human", "tool"),
            )
            return {
                "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)] + trimmed_messages,
            }
        if self.short_term_memory_strategy == "summarize":
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
            logger.debug(f"Summarization result: {summarization_result}")
            return self._prepare_state_update(context, summarization_result)
        raise ValueError(
            f"Invalid short_term_memory_strategy: {self.short_term_memory_strategy}"
        )


class PostModelNode(RunnableCallable):
    def __init__(self) -> None:
        super().__init__(self._func, self._afunc, name="post_model_node", trace=False)
        self.func_accepts_config = True

    def _func(self, input: dict[str, Any] | BaseModel) -> dict[str, Any]:
        raise NotImplementedError("Not implemented yet")

    async def _afunc(
        self,
        input: AgentState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        messages = input.get("messages")
        logger.debug(f"first: {messages[0]}")
        logger.debug(f"last: {messages[-1]}")
        payer = config.get("payer")
        if not payer:
            return {}
        return {"messages": messages}
