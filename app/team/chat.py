"""Team API chat thread and message endpoints."""

import asyncio
import logging
import textwrap

from epyxid import XID
from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db, get_session
from intentkit.core.engine import execute_agent, stream_agent
from intentkit.core.task_registry import cancel_task, register_task, unregister_task
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatCreate,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageTable,
    ChatTable,
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
from app.team.agent import get_team_agent
from app.team.auth import verify_team_member

team_chat_router = APIRouter()

logger = logging.getLogger(__name__)


# =============================================================================
# Thread Management Endpoints
# =============================================================================


@team_chat_router.get(
    "/teams/{team_id}/agents/{aid}/chats",
    response_model=list[Chat],
    operation_id="team_list_chats",
    summary="List chat threads (Team)",
    tags=["Team Thread"],
)
async def list_chats(
    aid: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Get all chat threads for a team agent (all team members see all chats)."""
    _user_id, team_id = auth
    agent = await get_team_agent(aid, team_id)
    async with get_session() as db:
        results = await db.scalars(
            select(ChatTable)
            .where(ChatTable.agent_id == agent.id)
            .order_by(desc(ChatTable.updated_at))
            .limit(10)
        )
        return [Chat.model_validate(chat) for chat in results]


@team_chat_router.post(
    "/teams/{team_id}/agents/{aid}/chats",
    response_model=Chat,
    operation_id="team_create_chat",
    summary="Create chat thread (Team)",
    tags=["Team Thread"],
)
async def create_chat_thread(
    request: LocalChatCreateRequest | None = None,
    aid: str = Path(..., description="Agent ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Create a new chat thread for a team agent."""
    user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = ChatCreate(
        id=str(XID()),
        agent_id=aid,
        user_id=user_id,
        summary="",
        rounds=0,
    )
    _ = await chat.save()
    if request and should_summarize_first_message(request.first_message):
        await update_chat_summary_from_first_message(
            aid, chat.id, request.first_message or ""
        )
    full_chat = await Chat.get(chat.id)
    return full_chat


@team_chat_router.patch(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}",
    response_model=Chat,
    operation_id="team_update_chat",
    summary="Update chat thread (Team)",
    tags=["Team Thread"],
)
async def update_chat_thread(
    request: ChatUpdateRequest,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Update a chat thread for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise _chat_not_found()

    updated_chat = await chat.update_summary(request.summary)
    return updated_chat


@team_chat_router.delete(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="team_delete_chat",
    summary="Delete chat thread (Team)",
    tags=["Team Thread"],
)
async def delete_chat_thread(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Delete a chat thread for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise _chat_not_found()

    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Message Endpoints
# =============================================================================


@team_chat_router.get(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}/messages",
    response_model=ChatMessagesResponse,
    operation_id="team_list_messages",
    summary="List messages (Team)",
    tags=["Team Message"],
)
async def list_messages(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
    auth: tuple[str, str] = Depends(verify_team_member),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get message history for a team agent chat thread."""
    _user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise _chat_not_found()

    stmt = (
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
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


@team_chat_router.post(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}/messages",
    response_model=list[ChatMessage],
    operation_id="team_send_message",
    summary="Send message (Team)",
    tags=["Team Message"],
)
async def send_message(
    request: LocalChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Send a new message to a team agent chat thread."""
    user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise _chat_not_found()

    should_schedule_summary = await should_schedule_chat_summary(
        aid, chat_id, AuthorType.WEB
    )

    if not chat.summary:
        summary = textwrap.shorten(request.message, width=20, placeholder="...")
        _ = await chat.update_summary(summary)

    await chat.add_round()

    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        team_id=team_id,
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
                register_task(aid, chat_id, current_task)
            try:
                async for chunk in stream_agent(user_message):
                    yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"
                if should_schedule_summary:
                    schedule_chat_summary_title_update(aid, chat_id)
            except asyncio.CancelledError:
                logger.info("Stream cancelled for agent %s, chat %s", aid, chat_id)
                return
            finally:
                unregister_task(aid, chat_id)

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        response_messages = await execute_agent(user_message)
        if should_schedule_summary:
            schedule_chat_summary_title_update(aid, chat_id)
        return response_messages


@team_chat_router.post(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}/cancel",
    operation_id="team_cancel_message",
    summary="Cancel generation (Team)",
    tags=["Team Message"],
)
async def cancel_generation(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Cancel an in-progress generation for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(aid, team_id)
    cancelled = cancel_task(aid, chat_id)
    return {"cancelled": cancelled}


@team_chat_router.post(
    "/teams/{team_id}/agents/{aid}/chats/{chat_id}/messages/retry",
    response_model=list[ChatMessage],
    operation_id="team_retry_message",
    summary="Retry message (Team)",
    tags=["Team Message"],
)
async def retry_message(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
    auth: tuple[str, str] = Depends(verify_team_member),
):
    """Retry the last message in a team agent chat thread."""
    user_id, team_id = auth
    await get_team_agent(aid, team_id)

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise _chat_not_found()

    last = await db.scalar(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )

    if not last:
        raise IntentKitAPIError(
            status_code=404, key="NoMessagesFound", message="No messages found"
        )

    last_message = ChatMessage.model_validate(last)

    if (
        last_message.author_type == AuthorType.AGENT
        or last_message.author_type == AuthorType.SYSTEM
    ):
        last_user_message = await db.scalar(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == aid,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.author_type == AuthorType.WEB,
            )
            .order_by(desc(ChatMessageTable.created_at))
            .limit(1)
        )

        if not last_user_message:
            return [last_message]

        messages_after_user = await db.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == aid,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.created_at > last_user_message.created_at,
            )
            .order_by(ChatMessageTable.created_at)
        )

        messages_list = messages_after_user.all()
        if messages_list:
            return [ChatMessage.model_validate(msg) for msg in messages_list]
        else:
            return [last_message]

    if last_message.author_type == AuthorType.SKILL:
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.SKILL_INTERRUPTED,
            agent_id=aid,
            chat_id=chat_id,
            user_id=user_id,
            author_id=aid,
            thread_type=last_message.thread_type or AuthorType.WEB,
            reply_to=last_message.id,
            time_cost=0.0,
        )
        error_message = await error_message_create.save()
        return [last_message, error_message]

    retry_user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        team_id=team_id,
        message=last_message.message or "",
        attachments=last_message.attachments,
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

    response_messages = await execute_agent(retry_user_message)
    return response_messages


# =============================================================================
# Utility Endpoints
# =============================================================================


@team_chat_router.get(
    "/teams/{team_id}/agents/{aid}/skill/history",
    tags=["Team Message"],
    response_model=list[ChatMessage],
    operation_id="team_skill_history",
    summary="Skill History (Team)",
)
async def get_skill_history(
    aid: str = Path(..., description="Agent ID"),
    db: AsyncSession = Depends(get_db),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[ChatMessage]:
    """Get last 50 skill messages for a team agent."""
    _user_id, team_id = auth
    await get_team_agent(aid, team_id)

    result = await db.scalars(
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == aid,
            ChatMessageTable.author_type == AuthorType.SKILL,
        )
        .order_by(desc(ChatMessageTable.created_at))
        .limit(50)
    )
    messages = result.all()
    return [ChatMessage.model_validate(message) for message in messages[::-1]]


# =============================================================================
# Helpers
# =============================================================================


def _chat_not_found():
    return IntentKitAPIError(
        status_code=404, key="ChatNotFound", message="Chat not found"
    )
