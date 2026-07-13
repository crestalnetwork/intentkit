"""Tests for the custom history-compression middleware.

Covers the per-model cold/warm/hot thresholds, the idle-time tier selection,
round-aware compaction (strip first round, keep previous + current rounds,
summarize the middle), the full-compress extreme case, chunked summarization
for oversized input, and the fail-safe paths that must never destroy history.
"""

import time
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from intentkit.core.summarization import (
    SummarizationMiddleware,
    _is_summary,
    _strip_first_round,
    _summary_message,
)
from intentkit.models.llm import LLMModelInfo, LLMProvider

# ──────────────────────────────────────────────
# Fixtures and helpers
# ──────────────────────────────────────────────


def _model_info(context_length: int = 100_000, **overrides: Any) -> LLMModelInfo:
    return LLMModelInfo(
        id="test-model",
        name="Test Model",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("1"),
        output_price=Decimal("2"),
        context_length=context_length,
        output_length=8192,
        intelligence=3,
        speed=3,
        **overrides,
    )


def _middleware(
    model_info: LLMModelInfo | None = None,
    summary_texts: list[str] | None = None,
    summary_context_length: int = 1_000_000,
) -> tuple[SummarizationMiddleware, MagicMock]:
    """Build a middleware with a mocked summary model returning canned texts."""
    summary_model = MagicMock()
    responses = [AIMessage(content=t) for t in (summary_texts or ["SUMMARY"] * 20)]
    summary_model.ainvoke = AsyncMock(side_effect=responses)
    mw = SummarizationMiddleware(
        model_info=model_info or _model_info(compress_cold=1000),
        summary_model=summary_model,
        summary_model_info=_model_info(context_length=summary_context_length),
    )
    return mw, summary_model


def _round(
    idx: int, with_tools: bool = False, answer: str | None = None
) -> list[AnyMessage]:
    """One conversation round: user question, optional tool loop, text answer."""
    msgs: list[AnyMessage] = [HumanMessage(content=f"question {idx}", id=f"h{idx}")]
    if with_tools:
        msgs.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search",
                        "args": {},
                        "id": f"tc{idx}",
                        "type": "tool_call",
                    }
                ],
                id=f"a{idx}-tool",
            )
        )
        msgs.append(
            ToolMessage(content="tool result", tool_call_id=f"tc{idx}", id=f"t{idx}")
        )
    msgs.append(AIMessage(content=answer or f"answer {idx}", id=f"a{idx}"))
    return msgs


def _with_usage(msg: AnyMessage, total: int) -> AnyMessage:
    """Attach provider-reported usage to an AI message."""
    assert isinstance(msg, AIMessage)
    msg.usage_metadata = {
        "input_tokens": total - 10,
        "output_tokens": 10,
        "total_tokens": total,
    }
    return msg


async def _run(
    mw: SummarizationMiddleware,
    messages: list[AnyMessage],
    last_llm_at: float | None = None,
    todos: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {"messages": messages}
    if last_llm_at is not None:
        state["last_llm_at"] = last_llm_at
    if todos is not None:
        state["todos"] = todos
    result = await mw.abefore_model(cast(Any, state), cast(Any, None))
    assert result is not None  # always at least the last_llm_at update
    return result


def _compacted(update: dict[str, Any]) -> list[AnyMessage]:
    """The rebuilt message list from a compaction update."""
    msgs = update["messages"]
    assert isinstance(msgs[0], RemoveMessage)
    assert msgs[0].id == REMOVE_ALL_MESSAGES
    return msgs[1:]


def _ids(messages: list[AnyMessage]) -> list[str | None]:
    return [m.id for m in messages]


# ──────────────────────────────────────────────
# LLMModelInfo.compress_thresholds
# ──────────────────────────────────────────────


def test_threshold_defaults():
    info = _model_info(context_length=1_000_000)
    assert info.compress_thresholds() == (20_000, 500_000, 800_000)


def test_threshold_overrides():
    info = _model_info(
        context_length=1_000_000,
        compress_cold=30_000,
        compress_warm=100_000,
        compress_hot=200_000,
    )
    assert info.compress_thresholds() == (30_000, 100_000, 200_000)


def test_threshold_small_context_clamped():
    """cold <= warm <= hot must hold even when 50% of context is below the
    20k cold default."""
    info = _model_info(context_length=32_000)
    cold, warm, hot = info.compress_thresholds()
    assert (cold, warm, hot) == (16_000, 16_000, 25_600)
    assert cold <= warm <= hot


# ──────────────────────────────────────────────
# Idle-time tier selection
# ──────────────────────────────────────────────


def test_tier_selection():
    mw, _ = _middleware(
        _model_info(compress_cold=100, compress_warm=200, compress_hot=300)
    )
    now = time.time()
    assert mw._pick_threshold(None, now) == 100  # unknown -> cold
    assert mw._pick_threshold(now - 60, now) == 300  # 1 min -> hot
    assert mw._pick_threshold(now - 5 * 3600, now) == 200  # 5 h -> warm
    assert mw._pick_threshold(now - 2 * 86_400, now) == 100  # 2 d -> cold


# ──────────────────────────────────────────────
# Trigger behavior
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_trigger_below_threshold():
    mw, summary_model = _middleware()
    messages = _round(0) + _round(1) + [HumanMessage(content="hi", id="h2")]

    update = await _run(mw, messages)

    assert "messages" not in update
    assert isinstance(update["last_llm_at"], float)
    summary_model.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_reported_usage_drives_trigger():
    """Tiny texts but huge provider-reported usage must still trigger."""
    mw, _ = _middleware()  # cold = 1000
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)  # last_llm_at unknown -> cold tier

    assert "messages" in update


@pytest.mark.asyncio
async def test_hot_tier_defers_compaction_warm_and_cold_do_not():
    """The same history compacts or not depending on thread idle time."""
    info = _model_info(compress_cold=1000, compress_warm=5000, compress_hot=50_000)

    def fresh_messages() -> list[AnyMessage]:
        r2c = _round(2)
        _with_usage(r2c[-1], 10_000)
        return _round(0) + _round(1) + r2c + [HumanMessage(content="now", id="h3")]

    now = time.time()

    mw, _ = _middleware(info)
    hot = await _run(mw, fresh_messages(), last_llm_at=now - 60)
    assert "messages" not in hot  # 10k < hot 50k

    mw, _ = _middleware(info)
    warm = await _run(mw, fresh_messages(), last_llm_at=now - 5 * 3600)
    assert "messages" in warm  # 10k > warm 5k

    mw, _ = _middleware(info)
    cold = await _run(mw, fresh_messages(), last_llm_at=now - 2 * 86_400)
    assert "messages" in cold  # 10k > cold 1k


# ──────────────────────────────────────────────
# Round-aware compaction
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compaction_keeps_first_prev_current_summarizes_middle():
    mw, summary_model = _middleware(summary_texts=["MIDDLE SUMMARY"])
    r0 = _round(0, with_tools=True)
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = r0 + _round(1) + r2 + [HumanMessage(content="now", id="h3")]
    todos = [{"content": "task", "status": "in_progress"}]

    update = await _run(mw, messages, todos=cast(Any, todos))

    compacted = _compacted(update)
    # First round stripped to user message + first text reply.
    assert compacted[0].id == "h0"
    assert compacted[1].id == "a0"
    assert "a0-tool" not in _ids(compacted)
    assert "t0" not in _ids(compacted)
    # Middle round replaced by the summary.
    assert "h1" not in _ids(compacted)
    assert _is_summary(compacted[2])
    assert "MIDDLE SUMMARY" in str(compacted[2].content)
    # Previous round and current round preserved in order.
    assert _ids(compacted[3:]) == ["h2", "a2", "h3"]
    # Todos snapshotted at compaction time.
    assert update["todos_snapshot"] == todos
    # The summarizer only saw the middle round.
    prompt = summary_model.ainvoke.await_args_list[0].args[0]
    assert "question 1" in prompt
    assert "question 0" not in prompt
    assert "question 2" not in prompt


@pytest.mark.asyncio
async def test_compaction_strips_preserved_usage_metadata():
    """Stale pre-compaction usage on kept messages must not re-trigger."""
    mw, _ = _middleware(summary_texts=["S"])
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    compacted = _compacted(update)
    for msg in compacted:
        if isinstance(msg, AIMessage):
            assert msg.usage_metadata is None

    # Regression: running again on the compacted history must not compact.
    mw2, summary_model2 = _middleware()
    update2 = await _run(mw2, compacted)
    assert "messages" not in update2
    summary_model2.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_round_plain_reply_kept_as_is():
    """A first round that is already user + text reply keeps its messages."""
    mw, _ = _middleware(summary_texts=["S"])
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    compacted = _compacted(await _run(mw, messages))

    assert compacted[0].content == "question 0"
    assert compacted[1].content == "answer 0"


def test_strip_first_round_skips_tool_loop_narration():
    """Text on a tool-calling message is narration; the first real reply is
    the first text-bearing message without tool calls."""
    round_msgs = cast(
        list[AnyMessage],
        [
            HumanMessage(content="q", id="h"),
            AIMessage(
                content="let me check...",
                tool_calls=[{"name": "t", "args": {}, "id": "tc", "type": "tool_call"}],
                id="a1",
            ),
            ToolMessage(content="result", tool_call_id="tc", id="t1"),
            AIMessage(content="the answer", id="a2"),
        ],
    )

    kept, changed = _strip_first_round(round_msgs)

    assert changed is True
    assert _ids(kept) == ["h", "a2"]
    assert kept[1].content == "the answer"


def test_strip_first_round_falls_back_to_last_text_and_strips():
    """When every text-bearing message carries tool calls, keep the last one,
    rebuilt as clean text (no tool calls, no thinking blocks)."""
    round_msgs = cast(
        list[AnyMessage],
        [
            HumanMessage(content="q", id="h"),
            AIMessage(
                content=[
                    {"type": "reasoning", "reasoning": "let me think"},
                    {"type": "text", "text": "the answer"},
                ],
                tool_calls=[{"name": "t", "args": {}, "id": "tc", "type": "tool_call"}],
                id="a1",
            ),
            ToolMessage(content="result", tool_call_id="tc", id="t1"),
        ],
    )

    kept, changed = _strip_first_round(round_msgs)

    assert changed is True
    assert _ids(kept) == ["h", "a1"]
    reply = cast(AIMessage, kept[1])
    assert reply.content == "the answer"  # text only: no reasoning block
    assert reply.tool_calls == []


def test_strip_first_round_keeps_first_of_multiple_text_replies():
    round_msgs = cast(
        list[AnyMessage],
        [
            HumanMessage(content="q", id="h"),
            AIMessage(content="reply one", id="a1"),
            AIMessage(content="reply two", id="a2"),
        ],
    )

    kept, changed = _strip_first_round(round_msgs)

    assert changed is True
    assert _ids(kept) == ["h", "a1"]


def test_strip_first_round_noop_detection():
    round_msgs = cast(
        list[AnyMessage],
        [HumanMessage(content="q", id="h"), AIMessage(content="a", id="a")],
    )
    kept, changed = _strip_first_round(round_msgs)
    assert changed is False
    assert kept == round_msgs


# ──────────────────────────────────────────────
# Structural skip guards
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_when_only_current_round():
    """The in-progress round is never compacted, however large."""
    mw, summary_model = _middleware()
    messages: list[AnyMessage] = [
        HumanMessage(content="x" * 100_000, id="h0"),
        AIMessage(
            content="",
            tool_calls=[{"name": "t", "args": {}, "id": "tc", "type": "tool_call"}],
            id="a0",
        ),
        ToolMessage(content="y" * 100_000, tool_call_id="tc", id="t0"),
    ]

    update = await _run(mw, messages)

    assert "messages" not in update
    summary_model.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_when_history_is_only_an_old_summary():
    mw, summary_model = _middleware()
    messages: list[AnyMessage] = [
        _summary_message("old summary"),
        HumanMessage(content="x" * 100_000, id="h0"),
        AIMessage(content="working on it", id="a0"),
    ]

    update = await _run(mw, messages)

    assert "messages" not in update
    summary_model.ainvoke.assert_not_awaited()


# ──────────────────────────────────────────────
# Extreme case: kept rounds exceed the cold threshold
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_compress_when_kept_rounds_exceed_cold():
    mw, summary_model = _middleware(summary_texts=["FULL SUMMARY"])
    # Previous round alone is ~25k approx tokens, over cold=1000.
    r2 = _round(2, answer="y" * 100_000)
    _with_usage(r2[-1], 50_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    compacted = _compacted(update)
    # Everything before the current round collapsed into one summary.
    assert len(compacted) == 2
    assert _is_summary(compacted[0])
    assert "FULL SUMMARY" in str(compacted[0].content)
    assert compacted[1].id == "h3"
    # The summarizer saw all three history rounds.
    prompt = summary_model.ainvoke.await_args_list[0].args[0]
    assert "question 0" in prompt
    assert "question 1" in prompt
    assert "question 2" in prompt


# ──────────────────────────────────────────────
# Chunked summarization for oversized input
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oversized_middle_summarized_in_chunks():
    """Middle content larger than the summarizer's context folds over
    multiple calls: summarize a chunk, prepend the result to the next."""
    mw, summary_model = _middleware(
        summary_texts=["S1", "S2", "S3", "S4", "S5"],
        summary_context_length=4096,  # budget = max(2048, 4096*0.6) = 2457
    )
    middle = [
        msgs
        for i in range(1, 5)
        for msgs in _round(i, answer="middle content " + "z" * 3000)
    ]
    r5 = _round(5)
    _with_usage(r5[-1], 10_000)
    messages = _round(0) + middle + r5 + [HumanMessage(content="now", id="h6")]

    update = await _run(mw, messages)

    calls = summary_model.ainvoke.await_count
    assert calls >= 2
    # Each later call folds in the previous chunk's summary.
    second_prompt = summary_model.ainvoke.await_args_list[1].args[0]
    assert "S1" in second_prompt
    # The final summary message carries the last response.
    compacted = _compacted(update)
    summaries = [m for m in compacted if _is_summary(m)]
    assert len(summaries) == 1
    assert f"S{calls}" in str(summaries[0].content)


def test_cap_message_shrinks_oversized_tool_calls():
    """A message oversized through huge tool-call args (not text) must still
    shrink, or its chunk exceeds the summarizer context and compaction is
    skipped forever for that thread."""
    mw, _ = _middleware()
    msg = AIMessage(
        content="short text",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"data": "z" * 200_000},
                "id": "tc",
                "type": "tool_call",
            }
        ],
        id="a1",
    )
    assert mw._count_summary_tokens([msg]) > 1000

    capped = mw._cap_message(msg, 1000)

    assert mw._count_summary_tokens([capped]) <= 1100  # cap + message overhead
    assert cast(AIMessage, capped).tool_calls == []
    assert "short text" in str(capped.content)


@pytest.mark.asyncio
async def test_single_oversized_message_truncated_not_looping():
    """One message alone above the summarizer budget is truncated so the
    chunk fold terminates."""
    mw, summary_model = _middleware(
        summary_texts=["S1", "S2", "S3"],
        summary_context_length=4096,
    )
    r1 = _round(1, answer="w" * 50_000)  # single message far over budget
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + r1 + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    assert "messages" in update
    prompts = [c.args[0] for c in summary_model.ainvoke.await_args_list]
    assert any("[truncated for summarization]" in p for p in prompts)


# ──────────────────────────────────────────────
# Fail-safe paths
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarizer_failure_keeps_history():
    mw, summary_model = _middleware()
    summary_model.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    assert "messages" not in update
    assert "todos_snapshot" not in update
    assert isinstance(update["last_llm_at"], float)


@pytest.mark.asyncio
async def test_summarizer_empty_response_keeps_history():
    mw, _ = _middleware(summary_texts=["   "])
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    assert "messages" not in update


@pytest.mark.asyncio
async def test_empty_todos_snapshot_on_compaction():
    mw, _ = _middleware(summary_texts=["S"])
    r2 = _round(2)
    _with_usage(r2[-1], 10_000)
    messages = _round(0) + _round(1) + r2 + [HumanMessage(content="now", id="h3")]

    update = await _run(mw, messages)

    assert update["todos_snapshot"] == []


# ──────────────────────────────────────────────
# End-to-end integration through create_agent
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compaction_end_to_end_through_agent_graph():
    """Run the middleware inside a real create_agent graph with the project's
    AgentState (DeltaChannel reducer with REMOVE_ALL handling) and a
    checkpointer, and verify a cold-tier compaction rewrites the checkpointed
    history into stripped-first-round + summary + previous + current."""
    from itertools import cycle

    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import InMemorySaver

    from intentkit.abstracts.graph import AgentContext, AgentState
    from intentkit.models.chat import AuthorType

    def fresh_replies():
        # A cycled single AIMessage instance would keep one id and make the
        # reducer overwrite prior replies; yield a fresh message per call.
        i = 0
        while True:
            i += 1
            yield AIMessage(content=f"reply {i} " + "x" * 1000, id=f"reply-{i}")

    graph = create_agent(
        model=GenericFakeChatModel(messages=fresh_replies()),
        tools=[],
        middleware=[
            SummarizationMiddleware(
                model_info=_model_info(compress_cold=1000),
                summary_model=GenericFakeChatModel(
                    messages=cycle([AIMessage(content="THE SUMMARY")])
                ),
                summary_model_info=_model_info(),
            )
        ],
        state_schema=AgentState,
        context_schema=AgentContext,
        checkpointer=InMemorySaver(),
    )
    context = AgentContext(
        agent_id="a1",
        get_agent=lambda: MagicMock(),
        chat_id="c1",
        entrypoint=AuthorType.WEB,
        is_own_team=True,
    )
    config: Any = {"configurable": {"thread_id": "t1"}}

    # Four rounds (~260 approx tokens each): well past cold=1000 in total,
    # while first + previous round together stay below it.
    for i in range(4):
        await graph.ainvoke(
            {"messages": [HumanMessage(content=f"question {i}")]},
            config,
            context=context,
        )
    state = graph.get_state(config)
    assert state.values.get("last_llm_at"), "last_llm_at not checkpointed"
    assert len(state.values["messages"]) == 8  # nothing compacted while hot

    # Age the thread past the warm window so the cold threshold applies.
    graph.update_state(
        config, {"last_llm_at": state.values["last_llm_at"] - 2 * 86_400}
    )
    await graph.ainvoke(
        {"messages": [HumanMessage(content="question 4")]}, config, context=context
    )

    messages = graph.get_state(config).values["messages"]
    briefs = [str(m.content)[:12] for m in messages]
    assert briefs == [
        "question 0",  # first round kept
        "reply 1 xxxx",
        "Here is a su",  # middle rounds 1-2 summarized
        "question 3",  # previous round kept
        "reply 4 xxxx",
        "question 4",  # current round
        "reply 5 xxxx",
    ]
    assert _is_summary(messages[2])
    assert "THE SUMMARY" in str(messages[2].content)
    assert graph.get_state(config).values.get("todos_snapshot") == []
