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
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import AfterValidator, BaseModel

from intentkit.core.engine import execute_agent, stream_agent
from intentkit.core.lead.engine import execute_lead, stream_lead
from intentkit.core.lead.service import verify_team_membership
from intentkit.core.team.channel import (
    bind_channel_chat,
    set_push_channel,
    set_push_channel_if_empty,
    upsert_channel_config,
)
from intentkit.core.team.wechat_session_notice import (
    WECHAT_SESSION_EXPIRING,
    build_expiring_prompt,
)
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageCreate,
)
from intentkit.models.user import User, UserUpdate
from intentkit.utils.error import IntentKitAPIError

# Set of recognized system_trigger values. Each value supplies its own
# synthesized prompt and may override the author_type to TRIGGER so the
# event is recorded in chat history without looking like a real user message.
_SYSTEM_TRIGGERS: frozenset[str] = frozenset({WECHAT_SESSION_EXPIRING})

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
        yield "event: message\ndata: [DONE]\n\n"

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


class LeadMessageExecuteRequest(BaseModel):
    """Request body for executing the team lead with a pre-built message."""

    team_id: str
    user_id: str
    message: ChatMessageCreate


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/execute-lead", response_model=list[ChatMessage])
async def execute_lead_message(
    request: LeadMessageExecuteRequest = Body(...),
) -> list[ChatMessage]:
    """Execute the team lead with a pre-built message and return all results.

    Used by the autonomous scheduler so lead orchestration runs in the core
    service rather than in the scheduler process.
    """
    return await execute_lead(request.team_id, request.user_id, request.message)


class LeadExecuteRequest(BaseModel):
    """Unified request body for team lead execution from any channel."""

    team_id: str
    channel_type: str  # "telegram", "wechat", etc.
    channel_user_id: str  # channel-specific user identifier
    chat_id: str
    message: str
    attachments: list[ChatMessageAttachment] | None = None
    # When set, the integration is asking the lead agent to handle a
    # system-driven event (e.g. wechat reply window about to close) rather
    # than a real user message. The `message` field is replaced with a
    # synthesized prompt and the saved record is tagged AuthorType.TRIGGER.
    system_trigger: str | None = None


# Per-channel config: (user_lookup, bind_field, author_type, chat_id_prefix)
_CHANNEL_CONFIG: dict[
    str,
    tuple[str, str, AuthorType, str],
] = {
    "telegram": ("get_by_telegram_id", "telegram_id", AuthorType.TELEGRAM, "tg_team"),
    "wechat": ("get_by_wechat_id", "wechat_id", AuthorType.WECHAT, "wx_team"),
    "lark": ("get_by_lark_id", "lark_id", AuthorType.LARK, "lk_team"),
    "slack": ("get_by_slack_id", "slack_id", AuthorType.SLACK, "sl_team"),
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

    # System-driven trigger: replace the (likely empty) caller message with
    # a synthesized prompt and tag the saved record as TRIGGER so chat-UI
    # consumers can hide it the same way they hide autonomous task triggers.
    message_text = request.message
    saved_author_type = author_type
    if request.system_trigger:
        if request.system_trigger not in _SYSTEM_TRIGGERS:
            raise IntentKitAPIError(
                400,
                "Bad Request",
                f"Unknown system_trigger: {request.system_trigger}",
            )
        if request.system_trigger == WECHAT_SESSION_EXPIRING:
            message_text = await build_expiring_prompt(request.team_id)
        saved_author_type = AuthorType.TRIGGER

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=f"team-{request.team_id}",
        chat_id=f"{chat_prefix}:{request.team_id}:{request.chat_id}",
        user_id=user_id,
        author_id=user_id,
        author_type=saved_author_type,
        thread_type=author_type,
        message=message_text,
        attachments=request.attachments,
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


class ChannelBindRequest(BaseModel):
    """Request body for binding a chat to a team via a one-time bind token."""

    channel_type: str
    chat_id: str
    chat_name: str | None = None
    bind_token: str


# ⚠️ INTERNAL USE ONLY - bypasses auth for internal microservice calls.
@core_router.post("/lead/channel-bind")
async def channel_bind_endpoint(request: ChannelBindRequest = Body(...)):
    """Bind a chat to the team that owns the bind token. Called by shared bots.

    Returns the resolved team_id so the bot can route this chat immediately;
    404 if the token doesn't match an enabled centralized channel.
    """
    team_id = await bind_channel_chat(
        request.channel_type,
        request.chat_id,
        request.chat_name,
        request.bind_token,
    )
    if team_id is None:
        raise HTTPException(status_code=404, detail="Invalid or unknown bind token")
    return {"ok": True, "team_id": team_id}


class SetChannelConfigRequest(BaseModel):
    """Request body for storing a channel's OAuth install config."""

    team_id: str
    channel_type: str
    config: dict[str, object]
    created_by: str


# ⚠️ INTERNAL USE ONLY - bypasses auth for internal microservice calls.
@core_router.post("/lead/set-channel-config")
async def set_channel_config_endpoint(request: SetChannelConfigRequest = Body(...)):
    """Upsert a team channel's config (the OAuth install result). Called by the
    Lark webhook service after a tenant authorizes the app."""
    await upsert_channel_config(
        request.team_id,
        request.channel_type,
        request.config,
        created_by=request.created_by,
    )
    return {"ok": True}
