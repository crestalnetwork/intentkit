"""IntentKit Web API Router."""

import json
import logging
import secrets
import textwrap
from typing import List, Optional

from epyxid import XID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.config import config
from app.core.engine import execute_agent, thread_stats
from app.core.prompt import agent_prompt
from models.agent import Agent, AgentData
from models.chat import (
    AuthorType,
    Chat,
    ChatCreate,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageRequest,
    ChatMessageTable,
)
from models.db import get_db
from utils.middleware import create_jwt_middleware

# init logger
logger = logging.getLogger(__name__)

chat_router = APIRouter()
chat_router_readonly = APIRouter()

# Add security scheme
security = HTTPBasic()

# Create JWT middleware with admin config
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)


# Add credentials checker
def verify_debug_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    from app.config.config import config

    if not config.debug_auth_enabled:
        return None

    if not config.debug_username or not config.debug_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Debug credentials not configured",
        )

    is_username_correct = secrets.compare_digest(
        credentials.username.encode("utf8"), config.debug_username.encode("utf8")
    )
    is_password_correct = secrets.compare_digest(
        credentials.password.encode("utf8"), config.debug_password.encode("utf8")
    )

    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def format_debug_messages(messages: list[ChatMessage]) -> str:
    resp = ""
    for message in messages:
        if message.cold_start_cost:
            resp += "[ Agent cold start ... ]\n"
            resp += f"\n------------------- start cost: {message.cold_start_cost:.3f} seconds\n\n"
        if message.author_type == AuthorType.SKILL:
            resp += f"[ Skill Calls: ] ({message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC)\n\n"
            for skill_call in message.skill_calls:
                resp += f" {skill_call['name']}: {skill_call['parameters']}\n"
                if skill_call["success"]:
                    resp += f"  Success: {skill_call.get('response', '')}\n"
                else:
                    resp += f"  Failed: {skill_call.get('error_message', '')}\n"
            resp += (
                f"\n------------------- skill cost: {message.time_cost:.3f} seconds\n\n"
            )
        elif message.author_type == AuthorType.AGENT:
            resp += f"[ Agent: ] ({message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC)\n\n"
            resp += f" {message.message}\n"
            resp += (
                f"\n------------------- agent cost: {message.time_cost:.3f} seconds\n\n"
            )
        elif message.author_type == AuthorType.SYSTEM:
            resp += f"[ System: ] ({message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC)\n\n"
            resp += f" {message.message}\n"
            resp += f"\n------------------- system cost: {message.time_cost:.3f} seconds\n\n"
        else:
            resp += f"[ User: ] ({message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC) by {message.author_id}\n\n"
            resp += f" {message.message}\n"
            resp += (
                f"\n------------------- user cost: {message.time_cost:.3f} seconds\n\n"
            )
    return resp


@chat_router_readonly.get(
    "/debug/{agent_id}/chats/{chat_id}/memory",
    tags=["Debug"],
    response_class=Response,
    dependencies=[Depends(verify_debug_credentials)]
    if config.debug_auth_enabled
    else [],
    operation_id="debug_chat_memory",
    summary="Chat Memory",
)
async def debug_chat_memory(
    agent_id: str = Path(..., description="Agent id"),
    chat_id: str = Path(..., description="Chat id"),
) -> Response:
    """Get chat memory for debugging."""
    messages = await thread_stats(agent_id, chat_id)
    # Convert messages to format JSON
    formatted_json = json.dumps(
        [message.model_dump() for message in messages], indent=4
    )
    return Response(content=formatted_json, media_type="application/json")


@chat_router_readonly.get(
    "/debug/{agent_id}/chats/{chat_id}",
    tags=["Debug"],
    response_class=PlainTextResponse,
    dependencies=[Depends(verify_debug_credentials)]
    if config.debug_auth_enabled
    else [],
    operation_id="debug_chat_history",
    summary="Chat History",
)
async def debug_chat_history(
    agent_id: str = Path(..., description="Agent id"),
    chat_id: str = Path(..., description="Chat id"),
    db: AsyncSession = Depends(get_db),
) -> str:
    resp = f"Agent ID:\t{agent_id}\n\nChat ID:\t{chat_id}\n\n-------------------\n\n"
    messages = await get_chat_history(agent_id, chat_id, user_id=None, db=db)
    if messages:
        resp += format_debug_messages(messages)
    else:
        resp += "No messages\n"
    return resp


@chat_router.get(
    "/{aid}/chat", tags=["Debug"], response_class=PlainTextResponse, deprecated=True
)
async def debug_chat_deprecated(
    aid: str = Path(..., description="Agent ID"),
) -> str:
    return f"Deprecated: /{aid}/chat\n\nPlease use /debug/{aid}/chat instead"


@chat_router.get(
    "/debug/{aid}/chat",
    tags=["Debug"],
    response_class=PlainTextResponse,
    dependencies=[Depends(verify_debug_credentials)]
    if config.debug_auth_enabled
    else [],
    operation_id="debug_chat",
    summary="Chat",
)
async def debug_chat(
    request: Request,
    aid: str = Path(..., description="Agent ID"),
    q: str = Query(..., description="Query string"),
    debug: Optional[bool] = Query(None, description="Enable debug mode"),
    thread: Optional[str] = Query(
        None, description="Thread ID for conversation tracking", deprecated=True
    ),
    chat_id: Optional[str] = Query(
        None, description="Chat ID for conversation tracking"
    ),
) -> str:
    """Debug mode: Chat with an AI agent.

    **Process Flow:**
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `q` - User's input query
    * `debug` - Enable debug mode (show whole skill response)
    * `thread` - Thread ID for conversation tracking
    * `chat_id` - Chat ID for conversation tracking

    **Returns:**
    * `str` - Formatted chat response

    **Raises:**
    * `404` - Agent not found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    if not q:
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    # Get agent and validate quota
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {aid} not found")

    # get thread_id from request ip
    if not chat_id:
        chat_id = thread if thread else request.client.host
    user_input = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id=agent.owner,
        author_id="debug",
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=q,
    )

    # Execute agent and get response
    messages = await execute_agent(user_input, debug=debug)

    resp = f"Agent ID:\t{aid}\n\nChat ID:\t{chat_id}\n\n-------------------\n\n"
    resp += "[ Input: ]\n\n"
    resp += f" {q} \n\n-------------------\n\n"

    resp += format_debug_messages(messages)

    resp += "Total time cost: {:.3f} seconds".format(
        sum([message.time_cost + message.cold_start_cost for message in messages])
    )

    return resp


@chat_router_readonly.get(
    "/debug/{agent_id}/prompt",
    tags=["Debug"],
    response_class=PlainTextResponse,
    dependencies=[Depends(verify_debug_credentials)]
    if config.debug_auth_enabled
    else [],
    operation_id="debug_agent_prompt",
    summary="Agent Prompt",
)
async def debug_agent_prompt(
    agent_id: str = Path(..., description="Agent id"),
) -> str:
    """Get agent's init and append prompts for debugging."""
    agent = await Agent.get(agent_id)
    agent_data = await AgentData.get(agent_id)

    init_prompt = agent_prompt(agent, agent_data)
    append_prompt = agent.prompt_append or "None"

    full_prompt = (
        f"[Init Prompt]\n\n{init_prompt}\n\n[Append Prompt]\n\n{append_prompt}"
    )
    return full_prompt


@chat_router_readonly.get(
    "/agents/{aid}/chat/history",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=List[ChatMessage],
    operation_id="get_chat_history",
    summary="Chat History",
)
async def get_chat_history(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to get history for"),
    user_id: Optional[str] = Query(None, description="User ID"),
    db: AsyncSession = Depends(get_db),
) -> List[ChatMessage]:
    """Get last 50 messages for a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `chat_id` - Chat ID to get history for

    **Returns:**
    * `List[ChatMessage]` - List of chat messages, ordered by creation time ascending

    **Raises:**
    * `404` - Agent not found
    """
    # Get agent and check if exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get chat messages (last 50 in DESC order)
    result = await db.scalars(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(50)
    )
    messages = result.all()

    # If the user_id exists, check if the chat belongs to the user
    if user_id:
        for message in messages:
            if message.user_id == user_id:
                break
            if message.author_id == user_id:
                break
        else:
            raise HTTPException(status_code=403, detail="Chat not belongs to user")

    # Reverse messages to get chronological order
    messages = [ChatMessage.model_validate(message) for message in messages[::-1]]

    return messages


@chat_router.get(
    "/agents/{aid}/chat/retry",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=ChatMessage,
    operation_id="retry_chat_deprecated",
    deprecated=True,
    summary="Retry Chat",
)
async def retry_chat_deprecated(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to retry last message"),
    db: AsyncSession = Depends(get_db),
) -> ChatMessage:
    """Retry the last message in a chat.

    If the last message is from the agent, return it directly.
    If the last message is from a user, generate a new agent response.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `chat_id` - Chat ID to retry

    **Returns:**
    * `ChatMessage` - Agent's response message

    **Raises:**
    * `404` - Agent not found or no messages found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and check if exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get last message
    last = await db.scalar(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )
    if not last:
        raise HTTPException(status_code=404, detail="No messages found")

    last_message = ChatMessage.model_validate(last)

    # If last message is from agent, return it
    if (
        last_message.author_type == AuthorType.AGENT
        or last_message.author_type == AuthorType.SYSTEM
    ):
        return last_message

    if last_message.author_type == AuthorType.SKILL:
        error_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=aid,
            chat_id=chat_id,
            user_id=last_message.user_id,
            author_id=aid,
            author_type=AuthorType.SYSTEM,
            thread_type=last_message.author_type,
            reply_to=last_message.reply_to,
            message="You were interrupted after executing a skill. Please retry with caution to avoid repeating the skill.",
            attachments=None,
        )
        await error_message.save()
        return error_message

    # If last message is from user, generate a new agent response
    return await create_chat_deprecated()


@chat_router.put(
    "/agents/{aid}/chat/retry/v2",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=list[ChatMessage],
    operation_id="retry_chat_put_deprecated",
    summary="Retry Chat",
    deprecated=True,
)
@chat_router.post(
    "/agents/{aid}/chat/retry/v2",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=list[ChatMessage],
    operation_id="retry_chat",
    summary="Retry Chat",
)
async def retry_chat(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to retry last message"),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    """Retry the last message in a chat.

    If the last message is from the agent, return it directly.
    If the last message is from a user, generate a new agent response.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `chat_id` - Chat ID to retry

    **Returns:**
    * `List[ChatMessage]` - List of chat messages including the retried response

    **Raises:**
    * `404` - Agent not found or no messages found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and check if exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get last message
    last = await db.scalar(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )

    if not last:
        raise HTTPException(status_code=404, detail="No messages found")

    last_message = ChatMessage.model_validate(last)
    if (
        last_message.author_type == AuthorType.AGENT
        or last_message.author_type == AuthorType.SYSTEM
    ):
        return [last_message]

    if last_message.author_type == AuthorType.SKILL:
        error_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=aid,
            chat_id=chat_id,
            user_id=last_message.user_id,
            author_id=aid,
            author_type=AuthorType.SYSTEM,
            thread_type=last_message.author_type,
            reply_to=last_message.reply_to,
            message="You were interrupted after executing a skill. Please retry with caution to avoid repeating the skill.",
            attachments=None,
        )
        await error_message.save()
        return [last_message, error_message]

    # If last message is from user, generate a new agent response
    return await create_chat()


@chat_router.post(
    "/agents/{aid}/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=ChatMessage,
    operation_id="create_chat_deprecated",
    deprecated=True,
    summary="Chat",
)
async def create_chat_deprecated(
    request: ChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
) -> ChatMessage:
    """Create a private chat message and get agent's response.

    **Process Flow:**
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage
    5. Saves both input and output messages

    > **Note:** This is for internal/private use and may have additional features or fewer
    > restrictions compared to the public endpoint.

    **Path Parameters:**
    * `aid` - Agent ID

    **Request Body:**
    * `request` - Chat message request object

    **Returns:**
    * `ChatMessage` - Agent's response message

    **Raises:**
    * `404` - Agent not found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and validate quota
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {aid} not found")

    # Create user message
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=request.chat_id,
        user_id=request.user_id,
        author_id=request.user_id,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
    )

    # Execute agent
    response_messages = await execute_agent(user_message)

    # Create or active chat
    chat = await Chat.get(request.chat_id)
    if chat:
        await chat.add_round()
    else:
        chat = ChatCreate(
            id=request.chat_id,
            agent_id=aid,
            user_id=request.user_id,
            summary=textwrap.shorten(request.message, width=20, placeholder="..."),
            rounds=1,
        )
        await chat.save()

    return response_messages[-1]


@chat_router.post(
    "/agents/{aid}/chat/v2",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=list[ChatMessage],
    operation_id="chat",
    summary="Chat",
)
async def create_chat(
    request: ChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
) -> list[ChatMessage]:
    """Create a chat message and get agent's response.

    **Process Flow:**
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage
    5. Saves both input and output messages

    > **Note:** This is the public-facing endpoint with appropriate rate limiting
    > and security measures.

    **Path Parameters:**
    * `aid` - Agent ID

    **Request Body:**
    * `request` - Chat message request object

    **Returns:**
    * `List[ChatMessage]` - List of chat messages including both user input and agent response

    **Raises:**
    * `404` - Agent not found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and validate quota
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {aid} not found")

    # Create user message
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=request.chat_id,
        user_id=request.user_id,
        author_id=request.user_id,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
    )

    # Execute agent
    response_messages = await execute_agent(user_message)

    # Create or active chat
    chat = await Chat.get(request.chat_id)
    if chat:
        await chat.add_round()
    else:
        chat = ChatCreate(
            id=request.chat_id,
            agent_id=aid,
            user_id=request.user_id,
            summary=textwrap.shorten(request.message, width=20, placeholder="..."),
            rounds=1,
        )
        await chat.save()

    return response_messages


@chat_router_readonly.get(
    "/agents/{aid}/chats",
    response_model=List[Chat],
    summary="User Chat List",
    tags=["Chat"],
    operation_id="get_agent_chats",
)
async def get_agent_chats(
    aid: str = Path(..., description="Agent ID"),
    user_id: str = Query(..., description="User ID"),
):
    """Get chat list for a specific agent and user.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `user_id` - User ID

    **Returns:**
    * `List[Chat]` - List of chats for the specified agent and user

    **Raises:**
    * `404` - Agent not found
    """
    # Verify agent exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get chats by agent and user
    chats = await Chat.get_by_agent_user(aid, user_id)
    return chats


class ChatSummaryUpdate(BaseModel):
    """Request model for updating chat summary."""

    summary: str = Field(
        ...,
        description="New summary text for the chat",
        examples=["User asked about product features and pricing"],
        min_length=1,
    )


@chat_router.put(
    "/agents/{aid}/chats/{chat_id}",
    response_model=Chat,
    summary="Update Chat Summary",
    tags=["Chat"],
    deprecated=True,
    operation_id="update_chat_summary_deprecated",
)
@chat_router.patch(
    "/agents/{aid}/chats/{chat_id}",
    response_model=Chat,
    summary="Update Chat Summary",
    tags=["Chat"],
    operation_id="update_chat_summary",
)
async def update_chat_summary(
    update_data: ChatSummaryUpdate,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Update the summary of a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID
    * `chat_id` - Chat ID

    **Request Body:**
    * `update_data` - Summary update data (in request body)

    **Returns:**
    * `Chat` - Updated chat object

    **Raises:**
    * `404` - Agent or chat not found
    """
    # Verify agent exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get chat
    chat = await Chat.get(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify chat belongs to agent
    if chat.agent_id != aid:
        raise HTTPException(status_code=404, detail="Chat not found for this agent")

    # Update summary
    updated_chat = await chat.update_summary(update_data.summary)
    return updated_chat


@chat_router.delete(
    "/agents/{aid}/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Chat",
    tags=["Chat"],
    operation_id="delete_chat",
)
async def delete_chat(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Delete a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID
    * `chat_id` - Chat ID

    **Returns:**
    * `204 No Content` - Success

    **Raises:**
    * `404` - Agent or chat not found
    """
    # Verify agent exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get chat
    chat = await Chat.get(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify chat belongs to agent
    if chat.agent_id != aid:
        raise HTTPException(status_code=404, detail="Chat not found for this agent")

    # Delete chat
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@chat_router_readonly.get(
    "/agents/{aid}/skill/history",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=List[ChatMessage],
    operation_id="get_skill_history",
    summary="Skill History",
)
async def get_skill_history(
    aid: str = Path(..., description="Agent ID"),
    db: AsyncSession = Depends(get_db),
) -> List[ChatMessage]:
    """Get last 50 skill messages for a specific agent.

    **Path Parameters:**
    * `aid` - Agent ID

    **Returns:**
    * `List[ChatMessage]` - List of skill messages, ordered by creation time ascending

    **Raises:**
    * `404` - Agent not found
    """
    # Get agent and check if exists
    agent = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get skill messages (last 50 in DESC order)
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

    # Reverse messages to get chronological order
    messages = [ChatMessage.model_validate(message) for message in messages[::-1]]

    return messages


@chat_router_readonly.get(
    "/messages/{message_id}",
    tags=["Chat"],
    dependencies=[Depends(verify_jwt)],
    response_model=ChatMessage,
    operation_id="get_chat_message",
    summary="Get Chat Message",
    responses={
        status.HTTP_200_OK: {
            "description": "Successfully retrieved the chat message",
            "model": ChatMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "You don't have permission to access this message",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Message not found",
        },
    },
)
async def get_chat_message(
    message_id: str = Path(..., description="Message ID"),
    user_id: Optional[str] = Query(None, description="User ID for authorization check"),
) -> ChatMessage:
    """Get a specific chat message by its ID.

    **Path Parameters:**
    * `message_id` - Message ID

    **Query Parameters:**
    * `user_id` - Optional User ID for authorization check

    **Returns:**
    * `ChatMessage` - The requested chat message

    **Raises:**
    * `404` - Message not found
    * `403` - Forbidden if user_id doesn't match the message's user_id
    """
    message = await ChatMessage.get(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} not found",
        )

    # If user_id is provided, check if it matches the message's user_id
    if user_id and message.user_id and user_id != message.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this message",
        )

    return message
