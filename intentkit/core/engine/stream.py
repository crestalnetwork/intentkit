"""Agent execution stream orchestration.

Validates the incoming message (payment, budget, media capability), prepares
multimodal input, drives the LangGraph stream loop and routes chunks to the
handlers in ``intentkit.core.engine.chunks``; error handling and checkpoint
recovery live in ``intentkit.core.engine.recovery``.
"""

import asyncio
import logging
import re
import time
import traceback
from contextlib import nullcontext
from typing import Any

import httpcore
import httpx
from epyxid import XID
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.exc import SQLAlchemyError

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.config.config import config
from intentkit.config.tracing import (
    propagate_trace_attributes,
    record_conversation_cache_hit_rate,
)
from intentkit.core.agent import get_agent
from intentkit.core.budget import check_hourly_budget_exceeded
from intentkit.core.chat import clear_thread_memory
from intentkit.core.engine.chunks import handle_model_chunk, handle_tools_chunk
from intentkit.core.engine.media import (
    FORWARDABLE_TYPES,
    MEDIA_INPUT_SPECS,
    build_image_url_block,
    build_v1_data_block,
    fetch_media_bytes,
)
from intentkit.core.engine.recovery import (
    cancel_cleanup,
    cleanup_empty_model_output,
    is_unrecoverable_checkpoint_error,
    summarize_history_messages,
)
from intentkit.core.executor import agent_executor
from intentkit.models.agent import Agent
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachmentType,
    ChatMessageCreate,
    sum_thread_token_usage,
)
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.llm import LLMModelInfo
from intentkit.models.user import User
from intentkit.utils.error import IntentKitAPIError, describe_provider_error

logger = logging.getLogger(__name__)


# Cap raw_chunks to prevent unbounded memory growth in long runs
_MAX_RAW_CHUNKS = 200


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
        thread_type=user_message.thread_entrypoint,
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
    if not payer:
        raise IntentKitAPIError(
            500,
            "PaymentError",
            "Payment is enabled but no team_id available for billing",
        )
    if agent.fee_percentage and agent.fee_percentage > 100:
        owner = await User.get(agent.owner) if agent.owner else None
        if owner and agent.fee_percentage > 100 + owner.nft_count * 10:
            return await _create_system_error_response(
                SystemMessageType.SERVICE_FEE_ERROR,
                user_message,
                time.perf_counter() - start,
            )
    # Fetch team credit account
    team_account = await CreditAccount.get_or_create(OwnerType.TEAM, payer)
    # As long as balance is positive, allow one conversation opportunity.
    # Credit can go negative during the conversation — that is acceptable.
    if team_account.balance <= 0:
        return await _create_system_error_response(
            SystemMessageType.INSUFFICIENT_BALANCE,
            user_message,
            time.perf_counter() - start,
        )
    return None


# Channels where the agent's own team pays (the requester isn't a billable team).
_AGENT_PAYS_CHANNELS = frozenset(
    {
        AuthorType.TELEGRAM,
        AuthorType.DISCORD,
        AuthorType.TWITTER,
        AuthorType.API,
        AuthorType.X402,
        AuthorType.TRIGGER,
    }
)


def _resolve_payer(message: ChatMessageCreate, agent: Agent) -> str | None:
    """Resolve the team account billed for this run.

    - Internal sub-agent calls (call_agent) carry an explicit ``payer`` so their
      cost flows back to the original caller's billing account; honor it.
    - Platform channels and autonomous triggers bill the agent's own team.
    - Normal user conversations bill the user's team (``message.team_id``).
    """
    if message.payer is not None:
        return message.payer
    if message.author_type in _AGENT_PAYS_CHANNELS:
        return agent.team_id
    return message.team_id


async def _resolve_team_names(*team_ids: str | None) -> dict[str, str]:
    """Resolve team id → display name via the cached team-info store.

    Best effort: tracing enrichment must never break an agent run, so a cache
    failure degrades to ids-only rather than raising.
    """
    wanted = {tid for tid in team_ids if tid}
    if not wanted:
        return {}
    try:
        from intentkit.core.team import get_team_infos

        infos = await get_team_infos(wanted)
        return {tid: info.name for tid, info in infos.items() if info.name}
    except Exception:
        logger.warning("Failed to resolve team names for tracing", exc_info=True)
        return {}


def build_stream_config(
    message: ChatMessageCreate,
    agent: Agent,
    team_id: str | None,
    thread_id: str,
    team_names: dict[str, str] | None = None,
) -> RunnableConfig:
    """Build the LangGraph run config for a chat stream.

    Sets a human-readable ``run_name`` — Langfuse uses it as the trace name,
    instead of the raw agent id the compiled graph is otherwise named with —
    plus a metadata block (env, agent, team, channel, …) that Langfuse attaches
    to every run for filtering. ``team_names`` maps team ids to display names
    (resolved by the caller via the cached team-info store) so traces show team
    names, not ids.

    ``message`` must be the pre-save message: ``call_depth`` is transient
    (not persisted), so a message re-validated from the DB would always report
    a depth of 0.
    """
    team_names = team_names or {}
    recursion_limit = config.recursion_limit

    agent_name = agent.name or message.agent_id
    owner_team_name = team_names.get(agent.team_id) if agent.team_id else None
    caller_team_name = team_names.get(team_id) if team_id else None
    # A public agent run triggered by a team other than the one that owns it.
    external_caller = bool(team_id and agent.team_id and team_id != agent.team_id)
    is_public = (
        agent.visibility is not None and agent.visibility >= AgentVisibility.PUBLIC
    )

    # A sub-agent run delegated via call_agent; the original user entry
    # channel is inherited through thread_entrypoint. Same definition as
    # AgentContext.is_subagent.
    is_subagent = message.call_depth > 0

    metadata: dict[str, Any] = {
        "env": config.env,
        "agent_id": message.agent_id,
        "agent_name": agent_name,
        "chat_id": message.chat_id,
        "thread_id": thread_id,
        # author_type/thread_type are already plain strings here (use_enum_values)
        "channel": message.thread_entrypoint,
        "model": agent.model,
        "visibility": "public" if is_public else "private",
    }
    if is_subagent:
        metadata["is_subagent"] = True
    if message.user_id:
        metadata["user_id"] = message.user_id
    if team_id:
        metadata["team_id"] = team_id
    if caller_team_name:
        metadata["team_name"] = caller_team_name
    if agent.team_id:
        metadata["agent_team_id"] = agent.team_id
    if owner_team_name:
        metadata["agent_team_name"] = owner_team_name
    if external_caller:
        metadata["external_caller"] = True
    if message.app_id:
        metadata["app_id"] = message.app_id
    # Langfuse groups traces by these reserved metadata keys and offers tags as
    # first-class filter chips. Only set when Langfuse tracing is active.
    if config.langfuse_tracing:
        metadata["langfuse_session_id"] = thread_id
        if message.user_id:
            metadata["langfuse_user_id"] = message.user_id
        tags = [
            config.env,
            message.thread_entrypoint,
            "public" if is_public else "private",
        ]
        if is_subagent:
            tags.append("subagent")
        if external_caller:
            tags.append("external-caller")
        metadata["langfuse_tags"] = tags

    run_name = f"{agent_name} ({owner_team_name})" if owner_team_name else agent_name

    return {
        "run_name": run_name,
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
        "metadata": metadata,
    }


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
            thread_type=user_message.thread_entrypoint,
            reply_to=user_message.id,
            message="Memory in context has been cleared.",
            time_cost=time.perf_counter() - start,
        )

        yield await confirmation_message.save()
        return

    model = await LLMModelInfo.get(agent.model)

    payment_enabled = config.payment_enabled

    # Determine payer team (needed for credit event recording regardless of
    # payment_enabled). Resolution lives in _resolve_payer for unit testing.
    payer = _resolve_payer(message, agent)

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

    # Is the agent operated by its owning team? Owner, same-team member, or
    # the system user qualify; anyone else is a guest of a published agent.
    is_own_team = False
    if user_message.user_id == agent.owner:
        is_own_team = True
    # Team-level access: if both team_ids exist and match
    # Use original message (not user_message) because team_id is excluded from DB persistence
    if message.team_id and agent.team_id and message.team_id == agent.team_id:
        is_own_team = True
    # Hack for local mode: treat the "system" user as the owning team.
    # This is safe because in authenticated environments,
    # user_id cannot be "system".
    if user_message.user_id == "system":
        is_own_team = True

    last = start

    # Group media URLs by attachment type and gate each on the model's
    # corresponding supports_<type>_input capability.
    media_urls_by_type: dict[ChatMessageAttachmentType, list[str]] = {
        atype: [] for atype, _, _ in MEDIA_INPUT_SPECS
    }
    if user_message.attachments:
        for att in user_message.attachments:
            atype = att.get("type")
            url = att.get("url")
            if atype in media_urls_by_type and url is not None:
                media_urls_by_type[atype].append(str(url))

    for atype, capability, error_type in MEDIA_INPUT_SPECS:
        if not media_urls_by_type[atype]:
            continue
        if not getattr(model, capability):
            yield await _create_system_error_response(
                error_type,
                user_message,
                time.perf_counter() - start,
            )
            return

    input_message = user_message.message

    # Append media attachment URLs as text so the LLM can reference them
    # across turns (e.g. when delegating to sub-agents later).
    if user_message.attachments:
        url_lines = []
        for att in user_message.attachments:
            att_type = att.get("type")
            att_url = att.get("url")
            if att_type in FORWARDABLE_TYPES and att_url:
                type_label = (
                    att_type.value
                    if isinstance(att_type, ChatMessageAttachmentType)
                    else att_type
                )
                url_lines.append(f"- [{type_label}] {att_url}")
        if url_lines:
            input_message += (
                "\n\n[Attachments in this message"
                " - use these URLs when delegating to other agents]\n"
                + "\n".join(url_lines)
            )

    # content to llm
    messages = [
        HumanMessage(content=input_message),
    ]
    # Image URLs ride straight through as `image_url` blocks; the LangChain
    # adapter handles the fetch. Audio/video/file get fetched here so we
    # can hand Gemini a `media` block with raw bytes + an explicit
    # mime_type, avoiding the empty-mimeType failure mode that the URL-only
    # data block path has produced in production.
    fetch_tasks: list = []
    fetch_meta: list[ChatMessageAttachmentType] = []
    for atype, _, _ in MEDIA_INPUT_SPECS:
        urls = media_urls_by_type[atype]
        if not urls:
            continue
        logger.info(
            "Passing %d %s url(s) to LLM for agent=%s chat=%s: %s",
            len(urls),
            atype.value,
            user_message.agent_id,
            user_message.chat_id,
            urls,
        )
        if atype == ChatMessageAttachmentType.IMAGE:
            messages.extend(
                HumanMessage(content=[build_image_url_block(url)]) for url in urls
            )
            continue
        for url in urls:
            fetch_tasks.append(fetch_media_bytes(url, atype))
            fetch_meta.append(atype)

    if fetch_tasks:
        try:
            fetched_media = await asyncio.gather(*fetch_tasks)
        except Exception:
            logger.exception(
                "Failed to fetch media attachments for agent=%s chat=%s",
                user_message.agent_id,
                user_message.chat_id,
            )
            yield await _create_system_error_response(
                SystemMessageType.AGENT_INTERNAL_ERROR,
                user_message,
                time.perf_counter() - start,
            )
            return
        messages.extend(
            HumanMessage(content=[build_v1_data_block(atype, fetched)])
            for atype, fetched in zip(fetch_meta, fetched_media, strict=True)
        )

    # stream config — pass the pre-save message so call_depth is populated
    thread_id = f"{user_message.agent_id}-{user_message.chat_id}"
    team_names = await _resolve_team_names(message.team_id, agent.team_id)
    stream_config = build_stream_config(
        message, agent, message.team_id, thread_id, team_names
    )

    def get_agent_for_context() -> Agent:
        return agent

    context = AgentContext(
        agent_id=user_message.agent_id,
        get_agent=get_agent_for_context,
        execute_agent=execute_agent,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        team_id=message.team_id,
        app_id=user_message.app_id,
        entrypoint=user_message.thread_entrypoint,
        is_own_team=is_own_team,
        payer=payer if payment_enabled else None,
        start_message_id=user_message.id,
        start_message_attachments=user_message.attachments,
        call_depth=message.call_depth,
        # Single source of truth for the run's "now": the same clock the
        # rendered chat history shows for this message.
        run_started_at=user_message.created_at,
    )

    # Observation-level session/user attribution. Top-level runs only: nested
    # sub-agent runs execute inside the caller's context and inherit its
    # attributes, keeping the whole trace attributed to one conversation.
    trace_ctx = (
        propagate_trace_attributes(session_id=thread_id, user_id=user_message.user_id)
        if message.call_depth == 0
        else nullcontext()
    )

    # run
    yielded_any = False
    raw_chunks: list[Any] = []
    cached_tool_step = None
    in_tools_phase = False
    try:
        with trace_ctx:
            async for chunk in executor.astream(
                {"messages": messages},
                context=context,
                config=stream_config,
                stream_mode=["updates", "custom"],
                durability="exit",
            ):
                this_time = time.perf_counter()
                logger.debug("stream chunk: %s", chunk, extra={"thread_id": thread_id})
                if len(raw_chunks) < _MAX_RAW_CHUNKS:
                    raw_chunks.append(chunk)

                if isinstance(chunk, tuple) and len(chunk) == 2:
                    _, payload = chunk
                    chunk = payload

                if not isinstance(chunk, dict):
                    continue

                if "model" in chunk and "messages" in chunk["model"]:
                    (
                        model_msgs,
                        last,
                        cached_tool_step,
                        in_tools_phase,
                    ) = await handle_model_chunk(
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
                        # Pending tool frames are transient announcements, not
                        # run output — they must not mask an empty run.
                        if not m.pending:
                            yielded_any = True
                        yield m
                elif "tools" in chunk and "messages" in chunk["tools"]:
                    in_tools_phase = False
                    tools_msgs, last = await handle_tools_chunk(
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
                    pass
    except asyncio.CancelledError:
        logger.info(
            f"Agent execution cancelled for {user_message.agent_id}",
            extra={"thread_id": thread_id},
        )
        # Shield cleanup DB operations from cancellation propagation.
        # Without shield, awaits inside CancelledError handler also get cancelled,
        # causing SQLAlchemy connection termination errors.
        await asyncio.shield(
            cancel_cleanup(
                executor,
                stream_config,
                in_tools_phase,
                user_message,
                thread_id,
                start,
            )
        )
        return
    except (TimeoutError, httpx.TimeoutException, httpcore.ReadTimeout):
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
            f"failed to execute agent: {e!s}\n{error_traceback}",
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
            f"failed to execute agent: {e!s}{describe_provider_error(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        # Only clear thread memory for known unrecoverable checkpoint corruption,
        # not for transient errors (LLM API failures, network issues, etc.)
        # that should preserve the conversation history.
        if is_unrecoverable_checkpoint_error(e):
            logger.warning(
                f"Clearing thread memory due to unrecoverable error for {user_message.agent_id}",
                extra={"thread_id": thread_id},
            )
            _ = await clear_thread_memory(user_message.agent_id, user_message.chat_id)
        return

    # If the stream completed normally but yielded zero messages,
    # the LLM likely returned an empty response (no content, no tool calls).
    # Typical cause: Gemini MALFORMED_FUNCTION_CALL — the malformed call isn't
    # in this turn's chunks, so dump recent history tool_calls for diagnosis
    # and prune the empty AIMessage so the thread isn't stuck on next turn.
    if not yielded_any:
        history_msgs = await cleanup_empty_model_output(
            executor,
            stream_config,
            user_message.agent_id,
            thread_id,
        )
        history_summary = summarize_history_messages(history_msgs)
        logger.error(
            f"Agent {user_message.agent_id} produced no output messages. "
            f"Total chunks received: {len(raw_chunks)}. "
            f"Raw chunks: {raw_chunks}. "
            f"Recent history ({len(history_summary)} of {len(history_msgs)} msgs): "
            f"{history_summary}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        return

    # Conversation-level cache hit rate: cumulative over the whole thread, as
    # a session score in Langfuse (the per-turn score lives on the trace).
    # Unlike the turn score — which covers every LLM call in the trace,
    # nested sub-agents included — this sums only this thread's own messages;
    # sub-agent calls live in their own threads.
    if config.langfuse_tracing and message.call_depth == 0:
        try:
            total_input, total_cached = await sum_thread_token_usage(
                user_message.agent_id, user_message.chat_id
            )
        except Exception:
            logger.warning(
                "Failed to sum thread token usage for tracing",
                extra={"thread_id": thread_id},
                exc_info=True,
            )
        else:
            record_conversation_cache_hit_rate(
                session_id=thread_id,
                input_tokens=total_input,
                cached_tokens=total_cached,
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
        debug (bool): Enable debug mode, will save the tool results

    Returns:
        list[ChatMessage]: Formatted response lines including timing information
    """
    resp = []
    async for chat_message in stream_agent(message):
        # Pending tool frames only matter to live consumers; a collected
        # result already contains the final tool messages.
        if chat_message.pending:
            continue
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
