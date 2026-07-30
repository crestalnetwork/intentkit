"""Stream chunk handlers: persist model/tool messages and record expenses."""

import logging
import textwrap
from datetime import datetime, timezone
from typing import Any

from epyxid import XID

from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.core.credit import expense_message, expense_tool
from intentkit.core.engine.content import (
    count_web_searches,
    extract_cached_input_tokens,
    extract_text_content,
    extract_thinking_content,
)
from intentkit.models.agent import Agent
from intentkit.models.chat import (
    DISPLAY_MESSAGE_ARG,
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageToolCall,
)
from intentkit.models.llm import LLMModelInfo, calculate_search_cost
from intentkit.tools.base import get_tool_price

logger = logging.getLogger(__name__)


def _lift_tool_call(call: dict[str, Any]) -> ChatMessageToolCall:
    """Base tool-call record from a model tool call.

    The injected status line travels in the call args; lift it out of
    ``parameters`` into its own field (see DISPLAY_MESSAGE_ARG).
    """
    parameters: dict[str, object] = dict(call["args"])
    display_message = parameters.pop(DISPLAY_MESSAGE_ARG, None)
    tool_call: ChatMessageToolCall = {
        "id": call.get("id") or "",
        "name": call["name"],
        "parameters": parameters,
    }
    if isinstance(display_message, str) and display_message.strip():
        tool_call["display_message"] = display_message.strip()
    return tool_call


def _build_pending_tool_message(
    tool_calls: list[dict[str, Any]],
    user_message: ChatMessage,
    agent: Agent,
) -> ChatMessage:
    """Transient frame announcing that the step's tool calls started.

    Yielded to live consumers before the tool node runs and never saved:
    the persisted tool message(s) that follow carry the same tool call ids,
    which is how consumers fold the results back into this frame.
    """
    return ChatMessage(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.TOOL,
        model=agent.model,
        thread_type=user_message.thread_entrypoint,
        reply_to=user_message.id,
        message="",
        tool_calls=[_lift_tool_call(call) for call in tool_calls],
        pending=True,
        created_at=datetime.now(timezone.utc),
    )


async def handle_model_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    model: LLMModelInfo,
    payer: str | None,
    this_time: float,
    last: float,
    thread_id: str,
    cached_tool_step: Any,
    in_tools_phase: bool,
) -> tuple[list[ChatMessage], float, Any, bool]:
    """Handle a stream chunk that contains ``model`` messages.

    Returns ``(messages_to_yield, updated_last, cached_tool_step, in_tools_phase)``.
    """
    messages_out: list[ChatMessage] = []

    if len(chunk["model"]["messages"]) != 1:
        logger.error(
            "unexpected model message: " + str(chunk["model"]["messages"]),
            extra={"thread_id": thread_id},
        )
    msg = chunk["model"]["messages"][0]
    has_tools = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
    if has_tools:
        in_tools_phase = True
        cached_tool_step = msg
    content = extract_text_content(msg.content) if hasattr(msg, "content") else ""
    thinking = extract_thinking_content(msg)
    # Yield standalone thinking message for tool-call chunks
    if has_tools and thinking:
        thinking_message_create = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.THINKING,
            model=agent.model,
            thread_type=user_message.thread_entrypoint,
            reply_to=user_message.id,
            message=thinking,
        )
        thinking_message = await thinking_message_create.save()
        messages_out.append(thinking_message)
    if has_tools:
        # Announce the calls before the tool node runs so live consumers can
        # show the status lines immediately; the persisted results follow
        # under the same tool call ids.
        messages_out.append(
            _build_pending_tool_message(msg.tool_calls, user_message, agent)
        )
    if content and not has_tools:
        usage = getattr(msg, "usage_metadata", None) or {}
        chat_message_create = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.AGENT,
            model=agent.model,
            thread_type=user_message.thread_entrypoint,
            reply_to=user_message.id,
            message=content,
            thinking=thinking,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=extract_cached_input_tokens(msg),
            time_cost=this_time - last,
        )
        last = this_time
        async with get_session() as session:
            amount = await model.calculate_cost(
                chat_message_create.input_tokens,
                chat_message_create.output_tokens,
                chat_message_create.cached_input_tokens,
            )

            search_count = count_web_searches(msg, model.provider)
            if search_count > 0:
                search_cost = await calculate_search_cost(model.provider, search_count)
                logger.info(
                    "[%s] Web search: %s calls, provider=%s, cost=%s",
                    user_message.agent_id,
                    search_count,
                    model.provider.value,
                    search_cost,
                )
                amount += search_cost
            credit_event = await expense_message(
                session,
                team_id=payer or "",
                message_id=chat_message_create.id,
                start_message_id=user_message.id,
                base_llm_amount=amount,
                agent=agent,
                user_id=user_message.user_id,
            )
            logger.info("[%s] expense message: %s", user_message.agent_id, amount)
            # Reconciliation: log OpenRouter-reported cost alongside our
            # token-based calculation so discrepancies can be audited.
            or_cost = (getattr(msg, "response_metadata", None) or {}).get("cost")
            if or_cost is not None:
                logger.info(
                    "[%s] openrouter reported cost: %s",
                    user_message.agent_id,
                    or_cost,
                )
            chat_message_create.credit_event_id = credit_event.id
            chat_message_create.credit_cost = credit_event.total_amount
            chat_message = await chat_message_create.save_in_session(session)
            await session.commit()
            messages_out.append(chat_message)

    return messages_out, last, cached_tool_step, in_tools_phase


async def handle_tools_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    model: LLMModelInfo,
    payer: str | None,
    this_time: float,
    last: float,
    thread_id: str,
    cached_tool_step: Any,
) -> tuple[list[ChatMessage], float]:
    """Handle a stream chunk that contains ``tools`` messages.

    Returns ``(messages_to_yield, updated_last)``.
    """
    if not cached_tool_step:
        logger.error(
            "unexpected tools message: " + str(chunk["tools"]),
            extra={"thread_id": thread_id},
        )
        return [], last

    tool_calls: list[ChatMessageToolCall] = []
    cached_attachments: list[Any] = []
    have_first_call_in_cache = False  # tool node emit every tool call
    for msg in chunk["tools"]["messages"]:
        if not hasattr(msg, "tool_call_id"):
            logger.error(
                "unexpected tools message: " + str(chunk["tools"]),
                extra={"thread_id": thread_id},
            )
            continue
        for call_index, call in enumerate(cached_tool_step.tool_calls):
            if call["id"] == msg.tool_call_id:
                if call_index == 0:
                    have_first_call_in_cache = True
                tool_call: ChatMessageToolCall = _lift_tool_call(call)
                tool_call["success"] = True
                status = getattr(msg, "status", None)
                if status == "error":
                    tool_call["success"] = False
                    tool_call["error_message"] = str(msg.content)
                else:
                    if config.debug:
                        tool_call["response"] = str(msg.content)
                    else:
                        tool_call["response"] = textwrap.shorten(
                            str(msg.content), width=1000, placeholder="..."
                        )
                    artifact = getattr(msg, "artifact", None)
                    if artifact:
                        cached_attachments.extend(artifact)
                tool_calls.append(tool_call)
                break

    tool_usage = getattr(cached_tool_step, "usage_metadata", None) or {}
    tool_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.TOOL,
        model=agent.model,
        thread_type=user_message.thread_entrypoint,
        reply_to=user_message.id,
        message="",
        tool_calls=tool_calls,
        attachments=cached_attachments,
        input_tokens=(
            tool_usage.get("input_tokens", 0) if have_first_call_in_cache else 0
        ),
        output_tokens=(
            tool_usage.get("output_tokens", 0) if have_first_call_in_cache else 0
        ),
        cached_input_tokens=(
            extract_cached_input_tokens(cached_tool_step)
            if have_first_call_in_cache
            else 0
        ),
        time_cost=this_time - last,
    )
    last = this_time
    async with get_session() as session:
        # 1. Message-level credit event (if applicable)
        if have_first_call_in_cache:
            message_amount = await model.calculate_cost(
                tool_message_create.input_tokens,
                tool_message_create.output_tokens,
                tool_message_create.cached_input_tokens,
            )
            message_payment_event = await expense_message(
                session,
                team_id=payer or "",
                message_id=tool_message_create.id,
                start_message_id=user_message.id,
                base_llm_amount=message_amount,
                agent=agent,
                user_id=user_message.user_id,
            )
            tool_message_create.credit_event_id = message_payment_event.id
            tool_message_create.credit_cost = message_payment_event.total_amount
        # 2. Per-tool credit events
        for tool_call in tool_calls:
            if not tool_call.get("success"):
                continue
            tool_price = get_tool_price(tool_call["name"])
            payment_event = await expense_tool(
                session,
                team_id=payer or "",
                message_id=tool_message_create.id,
                start_message_id=user_message.id,
                tool_call_id=tool_call.get("id", ""),
                tool_name=tool_call["name"],
                price=tool_price,
                agent=agent,
                user_id=user_message.user_id,
            )
            tool_call["credit_event_id"] = payment_event.id
            tool_call["credit_cost"] = payment_event.total_amount
            logger.info("[%s] tool payment: %s", user_message.agent_id, tool_call)
        # 3. Single insert with all credit info populated
        tool_message_create.tool_calls = tool_calls
        tool_message = await tool_message_create.save_in_session(session)
        await session.commit()
        return [tool_message], last
