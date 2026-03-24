"""Core API Router.

This module provides the core API endpoints for agent execution and management.

⚠️ SECURITY WARNING: INTERNAL USE ONLY ⚠️
These endpoints are designed for internal microservice communication only.
DO NOT expose these endpoints to the public internet.
DO NOT include this router in public-facing API documentation.
These endpoints bypass authentication and authorization checks for performance.
Use the public API endpoints in app/api.py for external access.
"""

from typing import Annotated

from epyxid import XID
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import AfterValidator, BaseModel

from intentkit.core.engine import execute_agent, stream_agent
from intentkit.core.lead.engine import stream_lead
from intentkit.core.lead.service import verify_team_membership
from intentkit.models.chat import AuthorType, ChatMessage, ChatMessageCreate
from intentkit.models.user import User, UserUpdate
from intentkit.utils.error import IntentKitAPIError

# ⚠️ INTERNAL API ONLY - DO NOT EXPOSE TO PUBLIC INTERNET ⚠️
core_router = APIRouter(
    prefix="/core",
    tags=["Core"],
    include_in_schema=False,  # Exclude from OpenAPI documentation
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
    """Execute an agent with the provided message and return all results.

    This endpoint executes an agent with the provided message and returns all
    generated messages as a complete list after execution finishes.

    **Request Body:**
    * `message` - The chat message containing agent_id, chat_id and message content

    **Response:**
    Returns a list of ChatMessage objects containing:
    * Skill call results (including tool executions)
    * Agent reasoning and responses
    * System messages or error notifications

    **Returns:**
    * `list[ChatMessage]` - Complete list of response messages

    **Raises:**
    * `HTTPException`:
        - 400: If input parameters are invalid
        - 404: If agent not found
        - 500: For other server-side errors
    """
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
    """Stream agent execution results in real-time using Server-Sent Events.

    This endpoint executes an agent with the provided message and streams the results
    in real-time using the SSE (Server-Sent Events) standard format.

    **Request Body:**
    * `message` - The chat message containing agent_id, chat_id and message content

    **Stream Format:**
    The response uses Server-Sent Events with the following format:
    * Event type: `message`
    * Data: ChatMessage object as JSON
    * Format: `event: message\\ndata: {ChatMessage JSON}\\n\\n`

    **Response Content:**
    Each streamed message can be:
    * Skill call results (including tool executions)
    * Agent reasoning and responses
    * System messages or error notifications

    **Returns:**
    * `StreamingResponse` - SSE stream with real-time ChatMessage objects

    **Raises:**
    * `HTTPException`:
        - 400: If input parameters are invalid
        - 404: If agent not found
        - 500: For other server-side errors
    """

    async def generate():
        async for chat_message in stream_agent(message):
            yield f"event: message\ndata: {chat_message.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


class TeamLeadExecuteRequest(BaseModel):
    """Request body for team lead execution from Telegram."""

    team_id: str
    telegram_id: str
    chat_id: str
    message: str


class WechatLeadExecuteRequest(BaseModel):
    """Request body for team lead execution from WeChat."""

    team_id: str
    wechat_user_id: str  # e.g. xxxxx@im.wechat
    chat_id: str
    message: str


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/lead/execute", response_model=list[ChatMessage])
async def execute_team_lead(
    request: TeamLeadExecuteRequest = Body(...),
) -> list[ChatMessage]:
    """Execute the team lead agent for a Telegram team channel message.

    Resolves telegram_id → IntentKit user, verifies team membership,
    and routes through stream_lead().
    """
    user = await User.get_by_telegram_id(request.telegram_id)
    if not user:
        raise IntentKitAPIError(
            403, "Forbidden", "Telegram user not bound to any IntentKit account"
        )

    await verify_team_membership(request.team_id, user.id)

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=request.team_id,
        chat_id=f"tg_team:{request.team_id}:{request.chat_id}",
        user_id=user.id,
        author_id=user.id,
        author_type=AuthorType.TELEGRAM,
        thread_type=AuthorType.TELEGRAM,
        message=request.message,
    )

    messages: list[ChatMessage] = []
    async for chat_message in stream_lead(request.team_id, user.id, chat_msg):
        messages.append(chat_message)

    return messages


# ⚠️ INTERNAL USE ONLY - This endpoint bypasses authentication for internal microservice calls
@core_router.post("/lead/wechat/execute", response_model=list[ChatMessage])
async def execute_wechat_team_lead(
    request: WechatLeadExecuteRequest = Body(...),
) -> list[ChatMessage]:
    """Execute the team lead agent for a WeChat team channel message.

    Attempts to resolve wechat_user_id → IntentKit user. If no bound user
    is found, uses the wechat_user_id directly as the user identity
    (supports local/single-user mode where user binding may not exist).
    """
    user = await User.get_by_wechat_id(request.wechat_user_id)
    if not user:
        # Auto-bind: set wechat_id on the team owner (local mode: "system" user)
        from intentkit.models.team import Team

        owner_id = await Team.get_owner(request.team_id)
        if owner_id:
            await UserUpdate.model_validate(
                {"wechat_id": request.wechat_user_id}
            ).patch(owner_id)
            user = await User.get(owner_id)

    if user:
        user_id = user.id
        await verify_team_membership(request.team_id, user_id)
    else:
        user_id = request.wechat_user_id

    chat_msg = ChatMessageCreate(
        id=str(XID()),
        agent_id=request.team_id,
        chat_id=f"wx_team:{request.team_id}:{request.chat_id}",
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.WECHAT,
        thread_type=AuthorType.WECHAT,
        message=request.message,
    )

    messages: list[ChatMessage] = []
    async for chat_message in stream_lead(request.team_id, user_id, chat_msg):
        messages.append(chat_message)

    return messages
