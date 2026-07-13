"""Conversation-history compression middleware.

Replaces LangChain's ``SummarizationMiddleware`` with an implementation
tailored to IntentKit's chat threads:

- **Time-tiered trigger.** The per-model ``compress_cold/warm/hot``
  thresholds (see ``LLMModelInfo.compress_thresholds``) are selected by how
  long ago the previous LLM request in this thread happened: within an hour
  the *hot* threshold applies (compress rarely, keep the prompt cache warm),
  within a day *warm*, and beyond that *cold* (the cache is gone anyway, so
  compress aggressively to cut input cost).
- **Round-aware compaction.** A "round" starts at each user message. The
  first round is kept but stripped down to the user message plus the agent's
  first text reply (tool calls and thinking dropped); the previous complete
  round and the in-progress current round are kept verbatim; everything in
  between is replaced by an LLM-written summary. When only one complete
  round exists it counts as the previous round and is kept whole. If the
  kept rounds alone would exceed the cold threshold, the whole history
  before the current round is summarized instead.
- **Chunked summarization.** When the text to summarize would not fit in
  the summarizer model's context, it is folded chunk by chunk: summarize the
  first chunk, prepend that summary to the next chunk, summarize again.
- **Fail-safe.** If the summarizer call fails, compaction is skipped and the
  full history is kept for this request — an error string must never
  replace real conversation history.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
)
from langchain_core.messages.utils import count_tokens_approximately, get_buffer_string
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.models.llm import LLMModelInfo

logger = logging.getLogger(__name__)

# Idle-time windows selecting which compression threshold applies.
HOT_WINDOW_SECONDS = 60 * 60
WARM_WINDOW_SECONDS = 24 * 60 * 60

# Marker on summary messages. Kept identical to LangChain's summarization
# middleware so summaries already checkpointed by the old implementation are
# still recognized (and re-compacted) by this one.
_SUMMARY_SOURCE_KEY = "lc_source"
_SUMMARY_SOURCE_VALUE = "summarization"

SUMMARY_PROMPT = """You are compacting an AI agent's conversation history. The messages below will be REPLACED by your summary, so it must capture everything the agent still needs to continue the conversation seamlessly.

Write the summary in the language predominantly used in the conversation.

Cover, when present:
1. The user's goals and requests — what they asked for, what was delivered, what is still pending.
2. Key facts, decisions, and conclusions, with the reasoning behind them.
3. Important tool results: data fetched, resources created or modified, identifiers, URLs, addresses, amounts.
4. User preferences and personal details revealed in the conversation.
5. Unresolved questions and agreed next steps.

Earlier summaries may appear among the messages; merge their content into one coherent summary instead of referring to them. Respond with the summary only — no preamble, no commentary.

<messages>
{messages}
</messages>"""


def _summary_message(text: str) -> HumanMessage:
    return HumanMessage(
        content=f"Here is a summary of the earlier conversation:\n\n{text}",
        additional_kwargs={_SUMMARY_SOURCE_KEY: _SUMMARY_SOURCE_VALUE},
        id=str(uuid.uuid4()),
    )


def _is_summary(msg: BaseMessage) -> bool:
    return (
        isinstance(msg, HumanMessage)
        and msg.additional_kwargs.get(_SUMMARY_SOURCE_KEY) == _SUMMARY_SOURCE_VALUE
    )


def _ensure_message_ids(messages: list[AnyMessage]) -> None:
    """Assign ids in place so the messages reducer can re-add them by identity."""
    for msg in messages:
        if not msg.id:
            msg.id = str(uuid.uuid4())


def _strip_stale_usage(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Drop ``usage_metadata`` from AI messages preserved across a compaction.

    Their reported ``total_tokens`` describes the context size *before*
    compaction; leaving it in place would make the next trigger check read a
    huge stale number and re-compact on every request.
    """
    return [
        msg.model_copy(update={"usage_metadata": None})
        if isinstance(msg, AIMessage) and msg.usage_metadata is not None
        else msg
        for msg in messages
    ]


@dataclass
class _CompactionPlan:
    """What a compaction pass keeps and what it summarizes.

    The rebuilt history is ``head + [summary of to_summarize] + tail`` (the
    summary message is omitted when ``to_summarize`` is empty).
    """

    head: list[AnyMessage]
    to_summarize: list[AnyMessage]
    tail: list[AnyMessage]


class SummarizationMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Compress checkpointed history before a model request when it exceeds
    the time-tiered threshold for the agent's model.

    Also snapshots the todo list whenever it compacts: compaction is the only
    mechanism that destroys ``write_todos`` tool results, and ``TodoMiddleware``
    re-injects the snapshot into the system prompt. Refreshing the snapshot
    only here keeps that prompt block stable between compactions, preserving
    prompt-cache hits.
    """

    def __init__(
        self,
        model_info: LLMModelInfo,
        summary_model: BaseChatModel,
        summary_model_info: LLMModelInfo,
    ) -> None:
        super().__init__()
        self.model_info = model_info
        self.summary_model = summary_model
        self.summary_model_info = summary_model_info
        self._cold, self._warm, self._hot = model_info.compress_thresholds()
        # Deliberately conservative (2 chars/token vs the usual ~4 for
        # English) for sizing the summarizer's input: overshooting the
        # summarizer's context fails the call, undershooting just splits the
        # work into one more chunk.
        self._count_summary_tokens = partial(
            count_tokens_approximately, chars_per_token=2.0
        )

    @override
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any] | None:
        del runtime
        now = time.time()
        update: dict[str, Any] = {"last_llm_at": now}

        messages = state["messages"]
        if not messages:
            return update

        threshold = self._pick_threshold(state.get("last_llm_at"), now)
        total_tokens = self._history_tokens(messages)
        if total_tokens <= threshold:
            return update

        # Ids are only load-bearing for re-adding messages after the
        # REMOVE_ALL reset, so the scan runs only when compaction may fire.
        _ensure_message_ids(messages)
        plan = self._plan_compaction(messages)
        if plan is None:
            return update

        compacted: list[AnyMessage] = list(plan.head)
        if plan.to_summarize:
            summary = await self._summarize(plan.to_summarize)
            if summary is None:
                # Summarizer failed — keep the full history rather than
                # destroying it. The next request retries.
                return update
            compacted.append(_summary_message(summary))
        compacted.extend(plan.tail)
        compacted = _strip_stale_usage(compacted)

        logger.info(
            "Compacted history for model %s: %d -> %d messages "
            "(~%d tokens over threshold %d)",
            self.model_info.id,
            len(messages),
            len(compacted),
            total_tokens,
            threshold,
        )
        update["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), *compacted]
        # Snapshot the todo list at the moment its tool-result echoes are
        # destroyed; TodoMiddleware re-injects it into the system prompt.
        update["todos_snapshot"] = state.get("todos") or []
        return update

    # ── trigger ──────────────────────────────────────────────

    def _pick_threshold(self, last_llm_at: float | None, now: float) -> int:
        """Select cold/warm/hot threshold from time since the previous request.

        An unknown timestamp (thread predates this feature) is treated as
        stale — the cold threshold applies. Brand-new threads are unaffected:
        their history is far below any threshold.
        """
        if last_llm_at is None:
            return self._cold
        elapsed = now - last_llm_at
        if elapsed <= HOT_WINDOW_SECONDS:
            return self._hot
        if elapsed <= WARM_WINDOW_SECONDS:
            return self._warm
        return self._cold

    def _history_tokens(self, messages: list[AnyMessage]) -> int:
        """Estimate the token size of the conversation history.

        Prefers the provider-reported usage of the most recent AI message
        that has one — the ground truth for context size at that point,
        including system prompt and tool schemas, and immune to the
        approximate counter's underestimation of CJK text — plus an
        approximate count of the messages after it. Falls back to a pure
        approximate count when no usage data is present (e.g. right after a
        compaction stripped it).
        """
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.usage_metadata is not None:
                total = msg.usage_metadata.get("total_tokens")
                if isinstance(total, int) and total > 0:
                    return total + count_tokens_approximately(messages[i + 1 :])
        return count_tokens_approximately(messages)

    # ── partitioning ─────────────────────────────────────────

    def _plan_compaction(self, messages: list[AnyMessage]) -> _CompactionPlan | None:
        """Decide what to keep and what to summarize.

        Rounds start at user messages (summary messages excluded). The
        current, possibly in-progress round is always kept verbatim — the
        model needs the live query and any pending tool-call pairs. Returns
        None when there is nothing worth compacting.
        """
        starts = [
            i
            for i, msg in enumerate(messages)
            if isinstance(msg, HumanMessage) and not _is_summary(msg)
        ]
        if not starts:
            return None
        current_start = starts[-1]
        history = messages[:current_start]
        if all(_is_summary(msg) for msg in history):
            # Nothing before the current round except (at most) an earlier
            # summary — re-summarizing it would gain nothing.
            return None
        tail_current = messages[current_start:]

        history_starts = starts[:-1]
        if not history_starts:
            # No complete round before the current one, but a non-summary
            # preamble exists (defensive; normal threads always start with a
            # user message): summarize the whole preamble.
            return _CompactionPlan(head=[], to_summarize=history, tail=tail_current)

        first_start = history_starts[0]
        prev_start = history_starts[-1]
        preamble = messages[:first_start]
        prev_round = messages[prev_start:current_start]

        if prev_start == first_start:
            # Only one complete round: it is both the first and the previous
            # round. Keeping it whole wins (it is the immediate context), so
            # only a preamble before it is summarizable.
            head: list[AnyMessage] = []
            first_kept_changed = False
            middle = preamble
        else:
            first_end = history_starts[1]
            head, first_kept_changed = _strip_first_round(
                messages[first_start:first_end]
            )
            middle = preamble + messages[first_end:prev_start]

        # Extreme case: the rounds we intend to keep are themselves larger
        # than the cold threshold — keeping them defeats the compaction, so
        # summarize the entire history before the current round instead.
        # Deliberately compared against cold even when the hot/warm tier
        # triggered: whatever survives a compaction must fit under the
        # strictest future threshold.
        if (
            count_tokens_approximately(head) + count_tokens_approximately(prev_round)
            > self._cold
        ):
            return _CompactionPlan(head=[], to_summarize=history, tail=tail_current)

        if not first_kept_changed and all(_is_summary(msg) for msg in middle):
            # Nothing stripped and nothing to summarize but earlier summaries
            # — a rebuild would change nothing meaningful, so skip. This also
            # breaks the re-summarize loop when the kept rounds alone sit
            # above the threshold but below the cold full-compress bar.
            return None

        return _CompactionPlan(
            head=head,
            to_summarize=middle,
            tail=prev_round + tail_current,
        )

    # ── summarization ────────────────────────────────────────

    async def _summarize(self, messages: list[AnyMessage]) -> str | None:
        """Summarize messages, folding chunk by chunk when they exceed the
        summarizer model's context. Returns None on failure."""
        try:
            budget = self._summary_input_budget()
            capped = [self._cap_message(msg, budget // 2) for msg in messages]
            summary: str | None = None
            for chunk in self._chunk_by_budget(capped, budget):
                if summary is not None:
                    chunk = [_summary_message(summary), *chunk]
                summary = await self._summarize_once(chunk)
            return summary
        except Exception:
            logger.exception(
                "History summarization failed for model %s; keeping full history",
                self.model_info.id,
            )
            return None

    def _summary_input_budget(self) -> int:
        """Token budget for one summarizer call.

        Half the summarizer's context: the other half is headroom for the
        prompt template, the completion, the fold summary prepended to later
        chunks (chunks are sized before folding), and the deliberate
        underestimation slack of the conservative counter.
        """
        return max(2048, int(self.summary_model_info.context_length * 0.5))

    def _cap_message(self, msg: AnyMessage, cap: int) -> AnyMessage:
        """Truncate a single message that alone exceeds the chunk budget, so
        chunking always terminates."""
        if self._count_summary_tokens([msg]) <= cap:
            return msg
        truncated = msg.text[: cap * 2] + "\n... [truncated for summarization]"
        update: dict[str, Any] = {"content": truncated}
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # Oversized tool-call payloads (huge args) must go too, or the
            # copy stays over the cap.
            update["tool_calls"] = []
        return msg.model_copy(update=update)

    def _chunk_by_budget(
        self, messages: list[AnyMessage], budget: int
    ) -> list[list[AnyMessage]]:
        """Greedily group messages into chunks that fit the summarizer budget."""
        chunks: list[list[AnyMessage]] = []
        current: list[AnyMessage] = []
        current_tokens = 0
        for msg in messages:
            msg_tokens = self._count_summary_tokens([msg])
            if current and current_tokens + msg_tokens > budget:
                chunks.append(current)
                current = []
                current_tokens = 0
            current.append(msg)
            current_tokens += msg_tokens
        if current:
            chunks.append(current)
        return chunks

    async def _summarize_once(self, messages: list[AnyMessage]) -> str:
        formatted = get_buffer_string(messages, format="xml")
        response = await self.summary_model.ainvoke(
            SUMMARY_PROMPT.format(messages=formatted),
            config={"metadata": {_SUMMARY_SOURCE_KEY: _SUMMARY_SOURCE_VALUE}},
        )
        text = response.text.strip()
        if not text:
            raise ValueError("summarizer returned empty text")
        return text


def _strip_first_round(
    round_msgs: list[AnyMessage],
) -> tuple[list[AnyMessage], bool]:
    """Reduce the first round to the user message plus the agent's first text
    reply, dropping tool calls, tool results, and thinking.

    Returns the kept messages and whether anything was actually dropped or
    stripped (used to detect no-op compactions).
    """
    kept: list[AnyMessage] = [round_msgs[0]]
    ai_texts = [
        msg for msg in round_msgs[1:] if isinstance(msg, AIMessage) and msg.text.strip()
    ]
    # The "first reply" is the first text the agent addressed to the user:
    # text carried on a tool-calling message is narration of the tool loop
    # being dropped ("let me check..."), so prefer the first text-bearing
    # message without tool calls and fall back to the last text-bearing one.
    reply = next(
        (msg for msg in ai_texts if not msg.tool_calls),
        ai_texts[-1] if ai_texts else None,
    )
    if reply is not None:
        if reply.tool_calls or not isinstance(reply.content, str):
            # Rebuild as a clean text-only message (same id) — drops tool
            # calls and structured thinking/reasoning blocks.
            kept.append(AIMessage(content=reply.text, id=reply.id, name=reply.name))
        else:
            kept.append(reply)
    changed = len(kept) < len(round_msgs) or (
        reply is not None and kept[-1] is not reply
    )
    return kept, changed


__all__ = [
    "HOT_WINDOW_SECONDS",
    "SUMMARY_PROMPT",
    "WARM_WINDOW_SECONDS",
    "SummarizationMiddleware",
]
