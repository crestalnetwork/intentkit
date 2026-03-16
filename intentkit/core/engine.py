"""AI Agent Management Module.

This module provides functionality for initializing and executing AI agents. It handles:
- Agent initialization with LangChain
- Tool and skill management
- Agent execution and response handling
- Memory management with PostgreSQL
- Integration with CDP and Twitter

The module uses a global cache to store initialized agents for better performance.
"""

# pyright: reportImportCycles=false

import asyncio
import logging
import re
import textwrap
import time
import traceback
from decimal import Decimal
from typing import Any, cast

import httpcore
import httpx
from epyxid import XID
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.exc import SQLAlchemyError

from intentkit.abstracts.graph import AgentContext, AgentError, AgentState
from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.core.agent import get_agent
from intentkit.core.budget import check_hourly_budget_exceeded
from intentkit.core.chat import clear_thread_memory
from intentkit.core.credit import expense_message, expense_skill
from intentkit.core.executor import (  # noqa: F401
    agent_executor,
    build_and_cache_executor,
    build_executor,
)
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentQuota
from intentkit.models.app_setting import AppSetting, SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageSkillCall,
)
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.llm import LLMModelInfo
from intentkit.models.user import User
from intentkit.skills.base import get_skill_price
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def _extract_thinking_content(msg: Any) -> str | None:
    """Extract reasoning/thinking content from a LangChain AIMessage.

    Handles multiple provider formats:
    - additional_kwargs["reasoning_content"] (OpenRouter, DeepSeek, xAI) — string
    - additional_kwargs["reasoning"]["summary"] (OpenAI Responses API v0 compat) — dict
    - content list: type="reasoning" with reasoning/summary/text (langchain-core, OpenAI)
    - content list: type="thinking" with thinking field (Anthropic, Google Gemini)
    """
    texts: list[str] = []

    # 1. Check additional_kwargs (OpenRouter, DeepSeek, xAI, OpenAI v0)
    kwargs = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(kwargs, dict):
        # OpenRouter / DeepSeek / xAI: reasoning_content is a string
        rc = kwargs.get("reasoning_content")
        if isinstance(rc, str) and rc:
            texts.append(rc)
        # OpenAI Responses API v0 compat: reasoning is a dict with summary list
        reasoning = kwargs.get("reasoning")
        if isinstance(reasoning, dict):
            for s in reasoning.get("summary", []):
                if isinstance(s, dict) and s.get("text"):
                    texts.append(s["text"])

    # 2. Check content blocks
    content = getattr(msg, "content", None)
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "reasoning":
                # langchain-core standard: text in "reasoning" field
                r = item.get("reasoning")
                if isinstance(r, str) and r:
                    texts.append(r)
                # OpenAI Responses API: summary list
                elif isinstance(item.get("summary"), list):
                    for s in item["summary"]:
                        if isinstance(s, dict) and s.get("text"):
                            texts.append(s["text"])
                # Fallback: direct text field
                elif item.get("text"):
                    texts.append(item["text"])
            elif item_type == "thinking":
                # Anthropic / Google Gemini: text in "thinking" field
                t = item.get("thinking")
                if isinstance(t, str) and t:
                    texts.append(t)

    return "\n\n".join(texts) if texts else None


def _extract_text_content(content: object) -> str:
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text")
                ty = item.get("type")
                if t is not None and (ty == "text" or ty is None):
                    texts.append(t)
            elif isinstance(item, str):
                texts.append(item)
        return "".join(texts)
    if isinstance(content, dict):
        if content.get("type") == "text" and "text" in content:
            return content["text"]
        if "text" in content:
            return content["text"]
        return ""
    if isinstance(content, str):
        return content
    return ""


def _extract_cached_input_tokens(msg: Any) -> int:
    """Extract cache_read token count from a LangChain message's usage_metadata."""
    if not hasattr(msg, "usage_metadata") or not msg.usage_metadata:
        return 0
    details = msg.usage_metadata.get("input_token_details")
    if not details:
        return 0
    return details.get("cache_read", 0)


async def stream_agent(message: ChatMessageCreate):
    """
    Stream agent execution results as an async generator.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content

    Yields:
        ChatMessage: Individual response messages including timing information
    """
    agent = await get_agent(message.agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )
    executor, cold_start_cost = await agent_executor(message.agent_id)
    message.cold_start_cost = cold_start_cost
    async for chat_message in stream_agent_raw(message, agent, executor):
        yield chat_message


async def _create_system_error_response(
    message_type: SystemMessageType,
    user_message: ChatMessage,
    time_cost: float,
) -> ChatMessage:
    """Create and save a system error/info message.

    This helper consolidates the repeated pattern of creating a
    ``ChatMessageCreate.from_system_message(...)`` and calling ``.save()``.
    """
    error_message_create = await ChatMessageCreate.from_system_message(
        message_type,
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id or "",
        author_id=user_message.agent_id,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        time_cost=time_cost,
    )
    return await error_message_create.save()


async def _validate_payment(
    user_message: ChatMessage,
    agent: Agent,
    payer: str | None,
    start: float,
) -> ChatMessage | None:
    """Validate payment preconditions.

    Returns ``None`` when validation passes, or a saved ``ChatMessage``
    error that the caller should yield and then return.
    """
    if not user_message.user_id or not agent.owner:
        raise IntentKitAPIError(
            500,
            "PaymentError",
            "Payment is enabled but user_id or agent owner is not set",
        )
    if agent.fee_percentage and agent.fee_percentage > 100:
        owner = await User.get(agent.owner)
        if owner and agent.fee_percentage > 100 + owner.nft_count * 10:
            return await _create_system_error_response(
                SystemMessageType.SERVICE_FEE_ERROR,
                user_message,
                time.perf_counter() - start,
            )
    # Fetch independent data concurrently
    user_account, quota, payment_settings = await asyncio.gather(
        CreditAccount.get_or_create(OwnerType.USER, payer or ""),
        AgentQuota.get(user_message.agent_id),
        AppSetting.payment(),
    )
    # agent abuse check
    abuse_check = True
    if (
        payment_settings.agent_whitelist_enabled
        and agent.id in payment_settings.agent_whitelist
    ):
        abuse_check = False
    if abuse_check and payer != agent.owner and user_account.free_credits > 0:
        if quota and quota.free_income_daily > 24000:
            return await _create_system_error_response(
                SystemMessageType.DAILY_USAGE_LIMIT_EXCEEDED,
                user_message,
                time.perf_counter() - start,
            )
    # avg cost
    avg_count = 1
    if quota and quota.avg_action_cost > 0:
        avg_count = quota.avg_action_cost
    if not user_account.has_sufficient_credits(Decimal(avg_count)):
        return await _create_system_error_response(
            SystemMessageType.INSUFFICIENT_BALANCE,
            user_message,
            time.perf_counter() - start,
        )
    return None


async def _handle_credit_check_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    this_time: float,
    last: float,
) -> tuple[list[ChatMessage], float]:
    """Handle a ``credit_check`` custom event chunk.

    Returns a list of messages to yield (possibly empty) and the updated
    ``last`` timestamp.  When the returned list is non-empty, the caller
    should yield all messages and then **return** from the generator (the
    credit-check event is terminal).
    """
    credit_payload = chunk.get("credit_check", {})
    content = credit_payload.get("message")
    if not content:
        return [], last

    credit_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.AGENT,
        model=agent.model,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        message=content,
        input_tokens=0,
        output_tokens=0,
        time_cost=this_time - last,
    )
    last = this_time
    credit_message = await credit_message_create.save()

    error_message = await _create_system_error_response(
        SystemMessageType.INSUFFICIENT_BALANCE,
        user_message,
        0,
    )
    return [credit_message, error_message], last


async def _handle_model_chunk(
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
    content = _extract_text_content(msg.content) if hasattr(msg, "content") else ""
    thinking = _extract_thinking_content(msg)
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
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message=thinking,
        )
        thinking_message = await thinking_message_create.save()
        messages_out.append(thinking_message)
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
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message=content,
            thinking=thinking,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=_extract_cached_input_tokens(msg),
            time_cost=this_time - last,
        )
        last = this_time
        async with get_session() as session:
            amount = await model.calculate_cost(
                chat_message_create.input_tokens,
                chat_message_create.output_tokens,
                chat_message_create.cached_input_tokens,
            )

            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                tool_outputs = msg.additional_kwargs.get("tool_outputs", [])
                for tool_output in tool_outputs:
                    if tool_output.get("type") == "web_search_call":
                        logger.info(
                            f"[{user_message.agent_id}] Found web_search_call in additional_kwargs"
                        )
                        amount += 35
                        break
            credit_event = await expense_message(
                session,
                payer or "",
                chat_message_create.id,
                user_message.id,
                amount,
                agent,
            )
            logger.info(f"[{user_message.agent_id}] expense message: {amount}")
            chat_message_create.credit_event_id = credit_event.id
            chat_message_create.credit_cost = credit_event.total_amount
            chat_message = await chat_message_create.save_in_session(session)
            await session.commit()
            messages_out.append(chat_message)

    return messages_out, last, cached_tool_step, in_tools_phase


async def _handle_tools_chunk(
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

    skill_calls: list[ChatMessageSkillCall] = []
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
                skill_call: ChatMessageSkillCall = {
                    "id": msg.tool_call_id,
                    "name": call["name"],
                    "parameters": call["args"],
                    "success": True,
                }
                status = getattr(msg, "status", None)
                if status == "error":
                    skill_call["success"] = False
                    skill_call["error_message"] = str(msg.content)
                else:
                    if config.debug:
                        skill_call["response"] = str(msg.content)
                    else:
                        skill_call["response"] = textwrap.shorten(
                            str(msg.content), width=1000, placeholder="..."
                        )
                    artifact = getattr(msg, "artifact", None)
                    if artifact:
                        cached_attachments.extend(artifact)
                skill_calls.append(skill_call)
                break

    tool_usage = getattr(cached_tool_step, "usage_metadata", None) or {}
    skill_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.SKILL,
        model=agent.model,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        message="",
        skill_calls=skill_calls,
        attachments=cached_attachments,
        input_tokens=(
            tool_usage.get("input_tokens", 0) if have_first_call_in_cache else 0
        ),
        output_tokens=(
            tool_usage.get("output_tokens", 0) if have_first_call_in_cache else 0
        ),
        cached_input_tokens=(
            _extract_cached_input_tokens(cached_tool_step)
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
                skill_message_create.input_tokens,
                skill_message_create.output_tokens,
                skill_message_create.cached_input_tokens,
            )
            message_payment_event = await expense_message(
                session,
                payer or "",
                skill_message_create.id,
                user_message.id,
                message_amount,
                agent,
            )
            skill_message_create.credit_event_id = message_payment_event.id
            skill_message_create.credit_cost = message_payment_event.total_amount
        # 2. Per-skill credit events
        for skill_call in skill_calls:
            if not skill_call["success"]:
                continue
            skill_price = get_skill_price(skill_call["name"])
            payment_event = await expense_skill(
                session,
                payer or "",
                skill_message_create.id,
                user_message.id,
                cast(str, skill_call.get("id", "")),
                skill_call["name"],
                skill_price,
                agent,
            )
            skill_call["credit_event_id"] = payment_event.id
            skill_call["credit_cost"] = payment_event.total_amount
            logger.info(f"[{user_message.agent_id}] skill payment: {skill_call}")
        # 3. Single insert with all credit info populated
        skill_message_create.skill_calls = skill_calls
        skill_message = await skill_message_create.save_in_session(session)
        await session.commit()
        return [skill_message], last


async def _handle_other_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    this_time: float,
    last: float,
) -> tuple[list[ChatMessage], float, bool]:
    """Handle the else-branch chunk looking for ``CreditCheckMiddleware.after_model``.

    Returns ``(messages_to_yield, updated_last, is_terminal)``.  When
    ``is_terminal`` is ``True``, the caller should yield all messages and
    then **return** from the generator.
    """
    for node_name, node_update in chunk.items():
        if (
            node_name.endswith("CreditCheckMiddleware.after_model")
            and isinstance(node_update, dict)
            and node_update.get("error") == AgentError.INSUFFICIENT_CREDITS
        ):
            ai_messages = [
                message
                for message in node_update.get("messages", [])
                if isinstance(message, BaseMessage)
            ]
            content = ""
            thinking = None
            if ai_messages:
                content = _extract_text_content(ai_messages[-1].content)
                thinking = _extract_thinking_content(ai_messages[-1])
            post_model_message_create = ChatMessageCreate(
                id=str(XID()),
                agent_id=user_message.agent_id,
                chat_id=user_message.chat_id,
                user_id=user_message.user_id,
                author_id=user_message.agent_id,
                author_type=AuthorType.AGENT,
                model=agent.model,
                thread_type=user_message.author_type,
                reply_to=user_message.id,
                message=content,
                thinking=thinking,
                input_tokens=0,
                output_tokens=0,
                time_cost=this_time - last,
            )
            last = this_time
            post_model_message = await post_model_message_create.save()

            error_message = await _create_system_error_response(
                SystemMessageType.INSUFFICIENT_BALANCE,
                user_message,
                0,
            )
            return [post_model_message, error_message], last, True
    return [], last, False


async def stream_agent_raw(
    message: ChatMessageCreate,
    agent: Agent,
    executor: CompiledStateGraph[AgentState, AgentContext, Any, Any],
):
    start = time.perf_counter()
    # make sure reply_to is set
    message.reply_to = message.id

    # save input message first
    user_message = await message.save()

    # temporary debug logging for telegram messages
    if user_message.author_type == AuthorType.TELEGRAM:
        logger.info(
            f"[TELEGRAM DEBUG] Agent: {user_message.agent_id} | Chat: {user_message.chat_id} | Message: {user_message.message}"
        )

    if re.search(
        r"(@clear|/clear)(?!\w)",
        user_message.message.strip(),
        re.IGNORECASE,
    ):
        _ = await clear_thread_memory(user_message.agent_id, user_message.chat_id)

        confirmation_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.AGENT,
            model=agent.model,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message="Memory in context has been cleared.",
            time_cost=time.perf_counter() - start,
        )

        yield await confirmation_message.save()
        return

    model = await LLMModelInfo.get(agent.model)

    payment_enabled = config.payment_enabled

    # Determine payer (needed for credit event recording regardless of payment_enabled)
    payer = user_message.user_id
    if user_message.author_type in [
        AuthorType.TELEGRAM,
        AuthorType.DISCORD,
        AuthorType.TWITTER,
        AuthorType.API,
        AuthorType.X402,
    ]:
        payer = agent.owner

    budget_status = await check_hourly_budget_exceeded(f"base_llm:{payer}")
    if budget_status.exceeded:
        yield await _create_system_error_response(
            SystemMessageType.HOURLY_BUDGET_EXCEEDED,
            user_message,
            time.perf_counter() - start,
        )
        return

    # check user balance
    if payment_enabled:
        payment_error = await _validate_payment(user_message, agent, payer, start)
        if payment_error is not None:
            yield payment_error
            return

    is_private = False
    if user_message.user_id == agent.owner:
        is_private = True
    # Hack for local mode: treat "system" user as private.
    # This is safe because in authenticated environments,
    # user_id cannot be "system".
    if user_message.user_id == "system":
        is_private = True

    last = start

    # Extract images from attachments
    image_urls = []
    if user_message.attachments:
        image_urls = [
            str(att["url"])
            for att in user_message.attachments
            if "type" in att
            and att["type"] == "image"
            and "url" in att
            and att["url"] is not None
        ]

    input_message = user_message.message

    # super mode — determined by agent config
    recursion_limit = config.recursion_limit
    if agent.super_mode:
        recursion_limit = max(config.super_recursion_limit, 1000)

    # content to llm
    messages = [
        HumanMessage(content=input_message),
    ]
    # if the model doesn't natively support image parsing, add the image URLs to the message
    if image_urls:
        if (
            agent.has_image_parser_skill(is_private=is_private)
            and not model.supports_image_input
        ):
            image_urls_text = "\n".join(image_urls)
            input_message += f"\n\nImages:\n{image_urls_text}"
            messages = [
                HumanMessage(content=input_message),
            ]
        else:
            # anyway, pass it directly to LLM
            messages.extend(
                [
                    HumanMessage(
                        content=[{"type": "image_url", "image_url": {"url": image_url}}]
                    )
                    for image_url in image_urls
                ]
            )

    # stream config
    thread_id = f"{user_message.agent_id}-{user_message.chat_id}"
    stream_config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
    }

    def get_agent() -> Agent:
        return agent

    context = AgentContext(
        agent_id=user_message.agent_id,
        get_agent=get_agent,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        app_id=user_message.app_id,
        entrypoint=user_message.author_type,
        is_private=is_private,
        payer=payer if payment_enabled else None,
        start_message_id=user_message.id,
    )

    # run
    yielded_any = False
    raw_chunks = []
    cached_tool_step = None
    in_tools_phase = False
    try:
        async for chunk in executor.astream(
            {"messages": messages},
            context=context,
            config=stream_config,
            stream_mode=["updates", "custom"],
        ):
            this_time = time.perf_counter()
            logger.debug(f"stream chunk: {chunk}", extra={"thread_id": thread_id})
            raw_chunks.append(chunk)

            if isinstance(chunk, tuple) and len(chunk) == 2:
                _, payload = chunk
                chunk = payload

            if isinstance(chunk, dict) and "credit_check" in chunk:
                credit_msgs, last = await _handle_credit_check_chunk(
                    chunk, user_message, agent, this_time, last
                )
                if credit_msgs:
                    yielded_any = True
                    for m in credit_msgs:
                        yield m
                    return

            if not isinstance(chunk, dict):
                continue

            if "model" in chunk and "messages" in chunk["model"]:
                (
                    model_msgs,
                    last,
                    cached_tool_step,
                    in_tools_phase,
                ) = await _handle_model_chunk(
                    chunk,
                    user_message,
                    agent,
                    model,
                    payer,
                    this_time,
                    last,
                    thread_id,
                    cached_tool_step,
                    in_tools_phase,
                )
                for m in model_msgs:
                    yielded_any = True
                    yield m
            elif "tools" in chunk and "messages" in chunk["tools"]:
                in_tools_phase = False
                tools_msgs, last = await _handle_tools_chunk(
                    chunk,
                    user_message,
                    agent,
                    model,
                    payer,
                    this_time,
                    last,
                    thread_id,
                    cached_tool_step,
                )
                for m in tools_msgs:
                    yielded_any = True
                    yield m
            else:
                other_msgs, last, is_terminal = await _handle_other_chunk(
                    chunk, user_message, agent, this_time, last
                )
                for m in other_msgs:
                    yielded_any = True
                    yield m
                if is_terminal:
                    return
    except asyncio.CancelledError:
        logger.info(
            f"Agent execution cancelled for {user_message.agent_id}",
            extra={"thread_id": thread_id},
        )
        if in_tools_phase:
            # Cancelled during tool execution — checkpoint has tool_calls without results.
            # Clear to prevent re-execution of tools on next message.
            await clear_thread_memory(user_message.agent_id, user_message.chat_id)
        # Save cancellation message directly (stream is already dead, can't yield)
        cancel_message_create = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.SYSTEM,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message="User cancelled the conversation",
            time_cost=time.perf_counter() - start,
        )
        await cancel_message_create.save()
        return
    except (httpx.TimeoutException, httpcore.ReadTimeout, asyncio.TimeoutError):
        logger.error(
            f"Agent request timed out for {user_message.agent_id}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.TIMEOUT_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        return
    except SQLAlchemyError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        return
    except GraphRecursionError:
        logger.error(
            f"Recursion limit reached for Agent {user_message.agent_id} (Thread: {thread_id}). Sending error message to chat.",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.RECURSION_LIMIT_EXCEEDED,
            user_message,
            time.perf_counter() - start,
        )
        return
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        _ = await clear_thread_memory(user_message.agent_id, user_message.chat_id)
        return

    # If the stream completed normally but yielded zero messages,
    # the LLM likely returned an empty response (no content, no tool calls).
    if not yielded_any:
        logger.error(
            f"Agent {user_message.agent_id} produced no output messages. "
            f"Total chunks received: {len(raw_chunks)}. "
            f"Raw chunks: {raw_chunks}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )


async def execute_agent(message: ChatMessageCreate) -> list[ChatMessage]:
    """
    Execute an agent with the given prompt and return response lines.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content
        debug (bool): Enable debug mode, will save the skill results

    Returns:
        list[ChatMessage]: Formatted response lines including timing information
    """
    resp = []
    async for chat_message in stream_agent(message):
        resp.append(chat_message)
    return resp


async def thread_stats(agent_id: str, chat_id: str) -> list[BaseMessage]:
    thread_id = f"{agent_id}-{chat_id}"
    from langchain_core.runnables import RunnableConfig

    stream_config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    executor, _ = await agent_executor(agent_id)
    snap = await executor.aget_state(stream_config)
    if snap.values and "messages" in snap.values:
        return snap.values["messages"]
    else:
        return []
