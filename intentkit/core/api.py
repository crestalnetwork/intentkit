"""Core API Router.

This module provides the core API endpoints for agent execution and management.

⚠️ SECURITY WARNING: INTERNAL USE ONLY ⚠️
These endpoints are designed for internal microservice communication only.
DO NOT expose these endpoints to the public internet.
DO NOT include this router in public-facing API documentation.
These endpoints bypass authentication and authorization checks for performance.
Use the public API endpoints in app/api.py for external access.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from epyxid import XID
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import AfterValidator, BaseModel

from intentkit.core.engine import execute_agent, stream_agent
from intentkit.core.lead.engine import stream_lead
from intentkit.core.lead.service import verify_team_membership
from intentkit.core.team.channel import set_push_channel, set_push_channel_if_empty
from intentkit.models.chat import AuthorType, ChatMessage, ChatMessageCreate
from intentkit.models.user import User, UserUpdate
from intentkit.utils.error import IntentKitAPIError

# ⚠️ INTERNAL API ONLY - DO NOT EXPOSE TO PUBLIC INTERNET ⚠️
core_router = APIRouter(
    prefix="/core",
    tags=["Core"],
    include_in_schema=False,  # Exclude from OpenAPI documentation
)


def _sse_response(gen: AsyncIterator[ChatMessage]) -> StreamingResponse:
    """Wrap an async ChatMessage iterator as an SSE StreamingResponse."""

    async def generate():
        async for chat_message in gen:
            yield f"event: message\ndata: {chat_message.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/execute", response_model=list[ChatMessage])
async def execute(
    message: Annotated[
        ChatMessageCreate, AfterValidator(ChatMessageCreate.model_validate)
    ] = Body(
        ...,
        description="The chat message containing agent_id, chat_id and message content",
    ),
) -> list[ChatMessage]:
    """Execute an agent with the provided message and return all results."""
    return await execute_agent(message)


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/stream")
async def stream(
    message: Annotated[
        ChatMessageCreate, AfterValidator(ChatMessageCreate.model_validate)
    ] = Body(
        ...,
        description="The chat message containing agent_id, chat_id and message content",
    ),
) -> StreamingResponse:
    """Stream agent execution results in real-time using Server-Sent Events."""
    return _sse_response(stream_agent(message))


class LeadExecuteRequest(BaseModel):
    """Unified request body for team lead execution from any channel."""

    team_id: str
    channel_type: str  # "telegram", "wechat", etc.
    channel_user_id: str  # channel-specific user identifier
    chat_id: str
    message: str


# Per-channel config: (user_lookup, bind_field, author_type, chat_id_prefix)
_CHANNEL_CONFIG: dict[
    str,
    tuple[str, str, AuthorType, str],
] = {
    "telegram": ("get_by_telegram_id", "telegram_id", AuthorType.TELEGRAM, "tg_team"),
    "wechat": ("get_by_wechat_id", "wechat_id", AuthorType.WECHAT, "wx_team"),
}


async def _resolve_lead(
    request: LeadExecuteRequest,
) -> tuple[str, ChatMessageCreate]:
    """Resolve channel user (with auto-bind) and build ChatMessageCreate for team lead."""
    cfg = _CHANNEL_CONFIG.get(request.channel_type)
    if not cfg:
        raise IntentKitAPIError(
            400, "Bad Request", f"Unsupported channel type: {request.channel_type}"
        )
    lookup_method, bind_field, author_type, chat_prefix = cfg

    user = await getattr(User, lookup_method)(request.channel_user_id)
    if not user:
        from intentkit.models.team import Team

        owner_id = await Team.get_owner(request.team_id)
        if owner_id:
            await UserUpdate.model_validate(
                {bind_field: request.channel_user_id}
            ).patch(owner_id)
            user = await User.get(owner_id)

    if user:
        user_id = user.id
        await verify_team_membership(request.team_id, user_id)
    else:
        user_id = request.channel_user_id

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=f"team-{request.team_id}",
        chat_id=f"{chat_prefix}:{request.team_id}:{request.chat_id}",
        user_id=user_id,
        author_id=user_id,
        author_type=author_type,
        thread_type=author_type,
        message=request.message,
    )
    return user_id, chat_msg


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/lead/execute", response_model=list[ChatMessage])
async def execute_team_lead(
    request: LeadExecuteRequest = Body(...),
) -> list[ChatMessage]:
    """Execute the team lead agent for a channel message."""
    user_id, chat_msg = await _resolve_lead(request)
    messages: list[ChatMessage] = []
    async for chat_message in stream_lead(request.team_id, user_id, chat_msg):
        messages.append(chat_message)
    return messages


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/lead/stream")
async def stream_team_lead(
    request: LeadExecuteRequest = Body(...),
) -> StreamingResponse:
    """Stream the team lead agent execution for a channel message."""
    user_id, chat_msg = await _resolve_lead(request)
    return _sse_response(stream_lead(request.team_id, user_id, chat_msg))


class SetPushChannelRequest(BaseModel):
    """Request body for setting the push channel target."""

    team_id: str
    channel_type: str
    chat_id: str
    if_empty: bool = False


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/lead/set-push-channel")
async def set_push_channel_endpoint(
    request: SetPushChannelRequest = Body(...),
):
    """Set the push channel target for a team. Called by Go integrations."""
    if request.if_empty:
        result = await set_push_channel_if_empty(
            request.team_id, request.channel_type, request.chat_id
        )
        return {"ok": True, "was_set": result}
    else:
        await set_push_channel(request.team_id, request.channel_type, request.chat_id)
        return {"ok": True}
