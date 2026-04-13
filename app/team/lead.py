"""Team API lead chat thread and message endpoints."""

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

from app.common.chat import (
    ChatMessagesResponse,
    ChatUpdateRequest,
    LocalChatCreateRequest,
    LocalChatMessageRequest,
    schedule_chat_summary_title_update,
    should_schedule_chat_summary,
    should_summarize_first_message,
    update_chat_summary_from_first_message,
)
from app.team.auth import verify_team_admin, verify_team_member

logger = logging.getLogger(__name__)

team_lead_router = APIRouter()

LEAD_AGENT_PREFIX = "team-"


def _lead_agent_id(team_id: str) -> str:
    return f"{LEAD_AGENT_PREFIX}{team_id}"


# =============================================================================
# Lead Agent Info Endpoint
# =============================================================================


@team_lead_router.get(
    "/teams/{team_id}/lead/info",
    response_model=Agent,
    operation_id="team_get_lead_info",
    summary="Get lead agent info (Team)",
    tags=["Lead"],
)
async def get_lead_info(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get lead agent details for the team."""
    _user_id, team_id = auth
    return await get_lead_agent(team_id)


# =============================================================================
# Thread Management Endpoints
# =============================================================================


@team_lead_router.get(
    "/teams/{team_id}/lead/chats",
    response_model=list[Chat],
    operation_id="team_list_lead_chats",
    summary="List lead chat threads (Team)",
    tags=["Lead"],
)
async def list_lead_chats(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get a list of lead chat threads for a team."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    return await Chat.get_by_agent_user(agent_id, user_id)


@team_lead_router.post(
    "/teams/{team_id}/lead/chats",
    response_model=Chat,
    operation_id="team_create_lead_chat",
    summary="Create lead chat thread (Team)",
    tags=["Lead"],
)
async def create_lead_chat_thread(
    request: LocalChatCreateRequest | None = None,
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Create a new lead chat thread for a team."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    chat = ChatCreate(
        id=str(XID()),
        agent_id=agent_id,
        user_id=user_id,
        summary="",
        rounds=0,
    )
    _ = await chat.save()
    if request and should_summarize_first_message(request.first_message):
        await update_chat_summary_from_first_message(
            agent_id, chat.id, request.first_message or ""
        )
    full_chat = await Chat.get(chat.id)
    return full_chat


@team_lead_router.patch(
    "/teams/{team_id}/lead/chats/{chat_id}",
    response_model=Chat,
    operation_id="team_update_lead_chat",
    summary="Update lead chat thread (Team)",
    tags=["Lead"],
)
async def update_lead_chat_thread(
    request: ChatUpdateRequest,
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Update a lead chat thread for a team."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != user_id:
        raise _chat_not_found()
    updated_chat = await chat.update_summary(request.summary)
    return updated_chat


@team_lead_router.delete(
    "/teams/{team_id}/lead/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="team_delete_lead_chat",
    summary="Delete lead chat thread (Team)",
    tags=["Lead"],
)
async def delete_lead_chat_thread(
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Delete a lead chat thread for a team."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != user_id:
        raise _chat_not_found()
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Message Endpoints
# =============================================================================


@team_lead_router.get(
    "/teams/{team_id}/lead/chats/{chat_id}/messages",
    response_model=ChatMessagesResponse,
    operation_id="team_list_lead_messages",
    summary="List lead messages (Team)",
    tags=["Lead"],
)
async def list_lead_messages(
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
    auth: tuple[str, str] = Depends(verify_team_member),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for a lead chat thread."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != user_id:
        raise _chat_not_found()

    stmt = (
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == agent_id,
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


@team_lead_router.post(
    "/teams/{team_id}/lead/chats/{chat_id}/messages",
    response_model=list[ChatMessage],
    operation_id="team_send_lead_message",
    summary="Send lead message (Team)",
    description=(
        "Send a new message to a lead chat thread. "
        "When `stream: true`, returns SSE stream with `event: message` events."
    ),
    tags=["Lead"],
)
async def send_lead_message(
    request: LocalChatMessageRequest,
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Send a new message to a lead chat thread."""
    user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != user_id:
        raise _chat_not_found()

    should_schedule_summary = await should_schedule_chat_summary(
        agent_id, chat_id, AuthorType.WEB
    )

    if not chat.summary:
        summary = textwrap.shorten(request.message, width=20, placeholder="...")
        _ = await chat.update_summary(summary)

    await chat.add_round()

    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=user_id,
        author_id=user_id,
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
                register_task(agent_id, chat_id, current_task)
            try:
                async for chunk in stream_lead(team_id, user_id, user_message):
                    yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"
                yield "event: message\ndata: [DONE]\n\n"
                if should_schedule_summary:
                    schedule_chat_summary_title_update(agent_id, chat_id)
            except asyncio.CancelledError:
                logger.info("Stream cancelled for lead chat %s", chat_id)
                return
            finally:
                unregister_task(agent_id, chat_id)

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        response_messages: list[ChatMessage] = []
        async for chunk in stream_lead(team_id, user_id, user_message):
            response_messages.append(chunk)
        if should_schedule_summary:
            schedule_chat_summary_title_update(agent_id, chat_id)
        return response_messages


@team_lead_router.post(
    "/teams/{team_id}/lead/chats/{chat_id}/cancel",
    operation_id="team_cancel_lead_generation",
    summary="Cancel lead generation (Team)",
    tags=["Lead"],
)
async def cancel_lead_generation(
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Cancel an in-progress lead generation."""
    _user_id, team_id = auth
    agent_id = _lead_agent_id(team_id)
    cancelled = cancel_task(agent_id, chat_id)
    return {"cancelled": cancelled}


# =============================================================================
# Channel Management Endpoints
# =============================================================================


@team_lead_router.get(
    "/teams/{team_id}/lead/channels",
    response_model=list[TeamChannel],
    operation_id="team_list_lead_channels",
    summary="List lead channel integrations (Team)",
    tags=["Lead"],
)
async def list_lead_channels(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get all configured channel integrations for the team lead agent."""
    _user_id, team_id = auth
    return await get_team_channels(team_id)


@team_lead_router.post(
    "/teams/{team_id}/lead/channels/{channel_type}",
    response_model=TeamChannel,
    operation_id="team_set_lead_channel",
    summary="Set a lead channel integration (Team)",
    tags=["Lead"],
)
async def set_lead_channel(
    channel_type: str = Path(..., description="Channel type (telegram, wechat)"),
    config: dict[str, object] = {},  # noqa: B006
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Create or update a channel integration for the team lead agent."""
    user_id, team_id = auth
    try:
        return await set_team_channel(team_id, channel_type, config, created_by=user_id)
    except (ValueError, ValidationError) as e:
        raise IntentKitAPIError(
            status_code=400, key="InvalidChannelConfig", message=str(e)
        )


@team_lead_router.delete(
    "/teams/{team_id}/lead/channels/{channel_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="team_delete_lead_channel",
    summary="Delete a lead channel integration (Team)",
    tags=["Lead"],
)
async def delete_lead_channel(
    channel_type: str = Path(..., description="Channel type (telegram, wechat)"),
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Remove a channel integration for the team lead agent."""
    _user_id, team_id = auth
    await remove_team_channel(team_id, channel_type)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@team_lead_router.get(
    "/teams/{team_id}/lead/channel/default",
    operation_id="team_get_lead_default_channel",
    summary="Get the default channel (Team)",
    tags=["Lead"],
)
async def get_lead_default_channel(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get the default notification channel type and chat ID for a team."""
    _user_id, team_id = auth
    channel_info = await get_default_channel(team_id)
    return channel_info


class SetDefaultChannelRequest(BaseModel):
    channel_type: str


@team_lead_router.put(
    "/teams/{team_id}/lead/channel/default",
    operation_id="team_set_lead_default_channel",
    summary="Set the default channel (Team)",
    tags=["Lead"],
)
async def set_lead_default_channel(
    body: SetDefaultChannelRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Switch the default notification channel for a team."""
    _user_id, team_id = auth
    try:
        await set_default_channel(team_id, body.channel_type)
    except ValueError as e:
        raise IntentKitAPIError(
            status_code=400, key="InvalidDefaultChannel", message=str(e)
        )
    return {"default_channel": body.channel_type}


@team_lead_router.get(
    "/teams/{team_id}/lead/channel/default/messages",
    response_model=ChatMessagesResponse,
    operation_id="team_list_lead_default_channel_messages",
    summary="List messages from the default channel (Team)",
    tags=["Lead"],
)
async def list_lead_default_channel_messages(
    auth: tuple[str, str] = Depends(verify_team_member),
    db: AsyncSession = Depends(get_db),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for the default channel chat."""
    _user_id, team_id = auth
    team = await db.get(TeamTable, team_id)
    if not team or not team.default_channel or not team.default_channel_chat_id:
        return ChatMessagesResponse(data=[], has_more=False, next_cursor=None)

    full_chat_id = build_channel_chat_id(
        team.default_channel, team_id, team.default_channel_chat_id
    )

    stmt = (
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == _lead_agent_id(team_id),
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


@team_lead_router.get(
    "/teams/{team_id}/lead/channels/telegram/status",
    response_model=TelegramStatus,
    operation_id="team_get_telegram_status",
    summary="Get Telegram channel status (Team)",
    tags=["Lead"],
)
async def get_telegram_status(
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get the Telegram channel status including verification code and whitelist."""
    _user_id, team_id = auth
    data = await TeamChannelData.get(team_id, "telegram")
    if not data or not data.data:
        return TelegramStatus()
    return TelegramStatus.from_data(data.data)


@team_lead_router.delete(
    "/teams/{team_id}/lead/channels/telegram/whitelist/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="team_remove_telegram_whitelist",
    summary="Remove a chat from Telegram whitelist (Team)",
    tags=["Lead"],
)
async def remove_telegram_whitelist(
    chat_id: str = Path(..., description="Telegram chat ID to remove"),
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Remove a chat from the Telegram channel whitelist."""
    _user_id, team_id = auth
    data = await TeamChannelData.get(team_id, "telegram")
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


def _chat_not_found():
    return IntentKitAPIError(
        status_code=404, key="ChatNotFound", message="Chat not found"
    )
