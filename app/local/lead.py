"""IntentKit Local Lead Chat API Router.

This module provides lead chat endpoints for local single-user development.
The lead chat uses hardcoded system IDs and delegates to stream_lead().
"""

import asyncio
import logging
import textwrap

from epyxid import XID
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db
from intentkit.core.lead import get_lead_agent, stream_lead
from intentkit.core.task_registry import cancel_task, register_task, unregister_task
from intentkit.core.team.channel import (
    build_channel_chat_id,
    get_default_channel,
    get_team_channels,
    remove_team_channel,
    set_default_channel,
    set_team_channel,
)
from intentkit.models.agent import Agent
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatCreate,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageTable,
)
from intentkit.models.team import TeamTable
from intentkit.models.team_channel import (
    TeamChannel,
    TeamChannelData,
    TelegramStatus,
)
from intentkit.utils.error import IntentKitAPIError

from app.local.chat import (
    ChatMessagesResponse,
    ChatUpdateRequest,
    LocalChatCreateRequest,
    LocalChatMessageRequest,
    schedule_chat_summary_title_update,
    should_schedule_chat_summary,
    should_summarize_first_message,
    update_chat_summary_from_first_message,
)

# init logger
logger = logging.getLogger(__name__)

lead_router = APIRouter()

# Hardcoded IDs for lead chat
LEAD_TEAM_ID = "system"
LEAD_USER_ID = "system"
LEAD_AGENT_ID = "system"


# =============================================================================
# Lead Agent Info Endpoint
# =============================================================================


@lead_router.get(
    "/lead/info",
    response_model=Agent,
    operation_id="get_lead_info",
    summary="Get lead agent info",
    tags=["Lead"],
)
async def get_lead_info():
    """Get lead agent details."""
    return await get_lead_agent(LEAD_TEAM_ID)


# =============================================================================
# Thread Management Endpoints
# =============================================================================


@lead_router.get(
    "/lead/chats",
    response_model=list[Chat],
    operation_id="list_lead_chats",
    summary="List lead chat threads",
    tags=["Lead"],
)
async def list_lead_chats():
    """Get a list of lead chat threads."""
    return await Chat.get_by_agent_user(LEAD_AGENT_ID, LEAD_USER_ID)


@lead_router.post(
    "/lead/chats",
    response_model=Chat,
    operation_id="create_lead_chat_thread",
    summary="Create a new lead chat thread",
    tags=["Lead"],
)
async def create_lead_chat_thread(
    request: LocalChatCreateRequest | None = None,
):
    """Create a new lead chat thread."""
    chat = ChatCreate(
        id=str(XID()),
        agent_id=LEAD_AGENT_ID,
        user_id=LEAD_USER_ID,
        summary="",
        rounds=0,
    )
    _ = await chat.save()
    if request and should_summarize_first_message(request.first_message):
        await update_chat_summary_from_first_message(
            LEAD_AGENT_ID, chat.id, request.first_message or ""
        )
    full_chat = await Chat.get(chat.id)
    return full_chat


@lead_router.patch(
    "/lead/chats/{chat_id}",
    response_model=Chat,
    operation_id="update_lead_chat_thread",
    summary="Update a lead chat thread",
    tags=["Lead"],
)
async def update_lead_chat_thread(
    request: ChatUpdateRequest,
    chat_id: str = Path(..., description="Chat ID"),
):
    """Update a lead chat thread."""
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != LEAD_AGENT_ID:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )
    updated_chat = await chat.update_summary(request.summary)
    return updated_chat


@lead_router.delete(
    "/lead/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_lead_chat_thread",
    summary="Delete a lead chat thread",
    tags=["Lead"],
)
async def delete_lead_chat_thread(
    chat_id: str = Path(..., description="Chat ID"),
):
    """Delete a lead chat thread."""
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != LEAD_AGENT_ID:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Message Endpoints
# =============================================================================


@lead_router.get(
    "/lead/chats/{chat_id}/messages",
    response_model=ChatMessagesResponse,
    operation_id="list_lead_messages",
    summary="List messages in a lead chat thread",
    tags=["Lead"],
)
async def list_lead_messages(
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for a lead chat thread."""
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != LEAD_AGENT_ID:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    stmt = (
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == LEAD_AGENT_ID,
            ChatMessageTable.chat_id == chat_id,
        )
        .order_by(desc(ChatMessageTable.id))
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(ChatMessageTable.id < cursor)
    result = await db.scalars(stmt)
    messages = result.all()
    has_more = len(messages) > limit
    messages_to_return = messages[:limit]
    next_cursor = (
        str(messages_to_return[-1].id) if has_more and messages_to_return else None
    )
    return ChatMessagesResponse(
        data=[ChatMessage.model_validate(m) for m in messages_to_return],
        has_more=has_more,
        next_cursor=next_cursor,
    )


@lead_router.post(
    "/lead/chats/{chat_id}/messages",
    response_model=list[ChatMessage],
    operation_id="send_lead_message",
    summary="Send a message to a lead chat thread",
    description=(
        "Send a new message to a lead chat thread. "
        "When `stream: true`, returns SSE stream with `event: message` events."
    ),
    tags=["Lead"],
)
async def send_lead_message(
    request: LocalChatMessageRequest,
    chat_id: str = Path(..., description="Chat ID"),
):
    """Send a new message to a lead chat thread."""
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != LEAD_AGENT_ID:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    should_schedule_summary = await should_schedule_chat_summary(
        LEAD_AGENT_ID, chat_id, AuthorType.WEB
    )

    # Update summary if it's empty
    if not chat.summary:
        summary = textwrap.shorten(request.message, width=20, placeholder="...")
        _ = await chat.update_summary(summary)

    # Increment the round count
    await chat.add_round()

    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=LEAD_AGENT_ID,
        chat_id=chat_id,
        user_id=LEAD_USER_ID,
        author_id=LEAD_USER_ID,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
        model=None,
        reply_to=None,
        skill_calls=None,
        input_tokens=0,
        output_tokens=0,
        time_cost=0.0,
        credit_event_id=None,
        credit_cost=None,
        cold_start_cost=0.0,
    )

    if request.stream:

        async def stream_gen():
            current_task = asyncio.current_task()
            if current_task:
                register_task(LEAD_AGENT_ID, chat_id, current_task)
            try:
                async for chunk in stream_lead(
                    LEAD_TEAM_ID, LEAD_USER_ID, user_message
                ):
                    yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"
                if should_schedule_summary:
                    schedule_chat_summary_title_update(LEAD_AGENT_ID, chat_id)
            except asyncio.CancelledError:
                logger.info("Stream cancelled for lead chat %s", chat_id)
                return
            finally:
                unregister_task(LEAD_AGENT_ID, chat_id)

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        # For non-streaming, collect all chunks from stream_lead
        response_messages: list[ChatMessage] = []
        async for chunk in stream_lead(LEAD_TEAM_ID, LEAD_USER_ID, user_message):
            response_messages.append(chunk)
        if should_schedule_summary:
            schedule_chat_summary_title_update(LEAD_AGENT_ID, chat_id)
        return response_messages


@lead_router.post(
    "/lead/chats/{chat_id}/cancel",
    operation_id="cancel_lead_generation",
    summary="Cancel an in-progress lead generation",
    tags=["Lead"],
)
async def cancel_lead_generation(
    chat_id: str = Path(..., description="Chat ID"),
):
    """Cancel an in-progress lead generation."""
    cancelled = cancel_task(LEAD_AGENT_ID, chat_id)
    return {"cancelled": cancelled}


# =============================================================================
# Channel Management Endpoints
# =============================================================================


@lead_router.get(
    "/lead/channels",
    response_model=list[TeamChannel],
    operation_id="list_lead_channels",
    summary="List lead channel integrations",
    tags=["Lead"],
)
async def list_lead_channels():
    """Get all configured channel integrations for the lead agent."""
    return await get_team_channels(LEAD_TEAM_ID)


@lead_router.post(
    "/lead/channels/{channel_type}",
    response_model=TeamChannel,
    operation_id="set_lead_channel",
    summary="Set a lead channel integration",
    tags=["Lead"],
)
async def set_lead_channel(
    channel_type: str = Path(..., description="Channel type (telegram, wechat)"),
    config: dict[str, object] = {},  # noqa: B006
):
    """Create or update a channel integration for the lead agent."""
    try:
        return await set_team_channel(
            LEAD_TEAM_ID, channel_type, config, created_by=LEAD_USER_ID
        )
    except (ValueError, ValidationError) as e:
        raise IntentKitAPIError(
            status_code=400, key="InvalidChannelConfig", message=str(e)
        )


@lead_router.delete(
    "/lead/channels/{channel_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_lead_channel",
    summary="Delete a lead channel integration",
    tags=["Lead"],
)
async def delete_lead_channel(
    channel_type: str = Path(..., description="Channel type (telegram, wechat)"),
):
    """Remove a channel integration for the lead agent."""
    await remove_team_channel(LEAD_TEAM_ID, channel_type)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@lead_router.get(
    "/lead/channel/default",
    operation_id="get_lead_default_channel",
    summary="Get the default channel for the lead agent",
    tags=["Lead"],
)
async def get_lead_default_channel():
    """Get the default notification channel type and chat ID."""
    channel_info = await get_default_channel(LEAD_TEAM_ID)
    return channel_info


class SetDefaultChannelRequest(BaseModel):
    channel_type: str


@lead_router.put(
    "/lead/channel/default",
    operation_id="set_lead_default_channel",
    summary="Set the default channel for the lead agent",
    tags=["Lead"],
)
async def set_lead_default_channel(
    body: SetDefaultChannelRequest = Body(...),
):
    """Switch the default notification channel."""
    try:
        await set_default_channel(LEAD_TEAM_ID, body.channel_type)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400, key="InvalidDefaultChannel", message=str(e)
        )
    return {"default_channel": body.channel_type}


@lead_router.get(
    "/lead/channel/default/messages",
    response_model=ChatMessagesResponse,
    operation_id="list_lead_default_channel_messages",
    summary="List messages from the default channel",
    tags=["Lead"],
)
async def list_lead_default_channel_messages(
    db: AsyncSession = Depends(get_db),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for the default channel chat."""
    team = await db.get(TeamTable, LEAD_TEAM_ID)
    if not team or not team.default_channel or not team.default_channel_chat_id:
        return ChatMessagesResponse(data=[], has_more=False, next_cursor=None)

    full_chat_id = build_channel_chat_id(
        team.default_channel, LEAD_TEAM_ID, team.default_channel_chat_id
    )

    stmt = (
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == LEAD_TEAM_ID,
            ChatMessageTable.chat_id == full_chat_id,
        )
        .order_by(desc(ChatMessageTable.id))
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(ChatMessageTable.id < cursor)
    result = await db.scalars(stmt)
    messages = result.all()
    has_more = len(messages) > limit
    messages_to_return = messages[:limit]
    next_cursor = (
        str(messages_to_return[-1].id) if has_more and messages_to_return else None
    )
    return ChatMessagesResponse(
        data=[ChatMessage.model_validate(m) for m in messages_to_return],
        has_more=has_more,
        next_cursor=next_cursor,
    )


# =============================================================================
# Telegram Status & Whitelist Endpoints
# =============================================================================


@lead_router.get(
    "/lead/channels/telegram/status",
    response_model=TelegramStatus,
    operation_id="get_telegram_status",
    summary="Get Telegram channel status",
    tags=["Lead"],
)
async def get_telegram_status():
    """Get the Telegram channel status including verification code and whitelist."""
    data = await TeamChannelData.get(LEAD_TEAM_ID, "telegram")
    if not data or not data.data:
        return TelegramStatus()
    return TelegramStatus.from_data(data.data)


@lead_router.delete(
    "/lead/channels/telegram/whitelist/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="remove_telegram_whitelist",
    summary="Remove a chat from Telegram whitelist",
    tags=["Lead"],
)
async def remove_telegram_whitelist(
    chat_id: str = Path(..., description="Telegram chat ID to remove"),
):
    """Remove a chat from the Telegram channel whitelist."""
    data = await TeamChannelData.get(LEAD_TEAM_ID, "telegram")
    if not data or not data.data:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raw_whitelist = data.data.get("whitelist")
    whitelist = list(raw_whitelist) if isinstance(raw_whitelist, list) else []
    data.data["whitelist"] = [
        e for e in whitelist if isinstance(e, dict) and e.get("chat_id") != chat_id
    ]
    await data.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Helpers
# =============================================================================
