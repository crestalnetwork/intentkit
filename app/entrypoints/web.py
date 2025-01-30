"""IntentKit Web API Router."""

import logging
from typing import List

from epyxid import XID
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, desc, select

from abstracts.engine import AgentMessageInput
from app.config.config import config
from app.core.engine import execute_agent
from models.agent import Agent, AgentQuota
from models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachmentType,
    ChatMessageRequest,
)
from models.db import get_db

# init logger
logger = logging.getLogger(__name__)

chat_router = APIRouter()


@chat_router.get("/{aid}/chat", tags=["Debug"], response_class=PlainTextResponse)
async def chat(
    request: Request,
    aid: str = Path(..., description="instance id"),
    q: str = Query(None, description="Query string"),
    debug: bool = Query(None, description="Enable debug mode"),
    thread: str = Query(None, description="Thread ID for conversation tracking"),
    db: Session = Depends(get_db),
):
    """Debug mode: Chat with an AI agent.

    This endpoint:
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage

    Args:
      - request: FastAPI request object
      - aid: Agent ID
      - q: User's input query
      - debug: Enable debug mode
      - thread: Thread ID for conversation tracking
      - db: Database session

    Returns:
      - str: Formatted chat response

    Raises:
      - HTTPException:
          - 404: Agent not found
          - 429: Quota exceeded
          - 500: Internal server error
    """
    # check if the agent quota is exceeded
    quota = AgentQuota.get(aid, db)
    if not quota.has_message_quota(db):
        raise HTTPException(
            status_code=429,
            detail=(
                "Message quota exceeded. Please upgrade your plan. "
                f"Daily: {quota.message_count_daily}/{quota.message_limit_daily}, "
                f"Monthly: {quota.message_count_monthly}/{quota.message_limit_monthly}, "
                f"Total: {quota.message_count_total}/{quota.message_limit_total}"
            ),
        )

    # get thread_id from query or request ip
    thread_id = (
        f"{aid}-{thread}" if thread is not None else f"{aid}-{request.client.host}"
    )
    logger.debug(f"thread id: {thread_id}")

    debug = debug if debug is not None else config.debug_resp

    # Execute agent and get response
    resp = execute_agent(aid, AgentMessageInput(text=q), thread_id, debug=debug)

    # only log if not in debug mode
    if not config.debug_resp:
        logger.info(resp)
    # reduce message quota
    quota.add_message(db)
    return "\n".join(resp)


@chat_router.get(
    "/agents/{aid}/chat/history", tags=["Chat"], response_model=List[ChatMessage]
)
async def get_chat_history(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to get history for"),
    db: Session = Depends(get_db),
) -> List[ChatMessage]:
    """Get chat history for a specific chat.

    Args:
      - aid: Agent ID
      - chat_id: Chat ID to get history for
      - db: Database session

    Returns:
      - List[ChatMessage]: List of chat messages, ordered by creation time ascending

    Raises:
      - HTTPException:
          - 404: Agent not found
    """
    # Get agent and check if exists
    agent = db.exec(select(Agent).where(Agent.id == aid)).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get chat messages (last 50 in DESC order)
    messages = db.exec(
        select(ChatMessage)
        .where(ChatMessage.agent_id == aid, ChatMessage.chat_id == chat_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(50)
    ).all()

    # Reverse messages to get chronological order
    messages.reverse()

    return messages


@chat_router.get("/agents/{aid}/chat/retry", tags=["Chat"], response_model=ChatMessage)
async def retry_chat(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to retry last message"),
    db: Session = Depends(get_db),
) -> ChatMessage:
    """Retry the last message in a chat.

    If the last message is from the agent, return it directly.
    If the last message is from a user, generate a new agent response.

    Args:
      - aid: Agent ID
      - chat_id: Chat ID to retry
      - db: Database session

    Returns:
      - ChatMessage: Agent's response message

    Raises:
      - HTTPException:
          - 404: Agent not found or no messages found
          - 429: Quota exceeded
          - 500: Internal server error
    """
    # Get agent and check if exists
    agent = db.exec(select(Agent).where(Agent.id == aid)).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get last message
    last_message = db.exec(
        select(ChatMessage)
        .where(ChatMessage.agent_id == aid, ChatMessage.chat_id == chat_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(1)
    ).first()

    if not last_message:
        raise HTTPException(status_code=404, detail="No messages found")

    # If last message is from agent, return it
    if last_message.author_type == AuthorType.AGENT:
        return last_message

    # Check quota before generating new response
    quota = AgentQuota.get(aid, db)
    if not quota.has_message_quota(db):
        raise HTTPException(status_code=429, detail="Message quota exceeded")

    try:
        # Extract image URLs from last message
        image_urls = [
            attachment.url
            for attachment in (last_message.attachments or [])
            if attachment.type == ChatMessageAttachmentType.IMAGE
        ]

        # Execute agent
        agent_input = AgentMessageInput(text=last_message.message, images=image_urls)
        response_lines = execute_agent(aid, agent_input, f"{aid}-{chat_id}")

        # Create agent's response message
        response_message = ChatMessage(
            id=str(XID()),
            agent_id=aid,
            chat_id=chat_id,
            author_id=aid,
            author_type=AuthorType.AGENT,
            message="\n".join(response_lines),
            attachments=None,
        )
        db.add(response_message)

        # Update quota
        quota.add_message(db)
        db.commit()
        db.refresh(response_message)

        return response_message

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/agents/{aid}/chat", tags=["Chat"], response_model=ChatMessage)
async def create_chat(
    request: ChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
    db: Session = Depends(get_db),
) -> ChatMessage:
    """Create a chat message and get agent's response.

    This endpoint:
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage
    5. Saves both input and output messages

    Args:
      - request: Chat message request
      - aid: Agent ID
      - db: Database session

    Returns:
      - ChatMessage: Agent's response message

    Raises:
      - HTTPException:
          - 404: Agent not found
          - 429: Quota exceeded
          - 500: Internal server error
    """
    # Get agent and check if exists
    agent = db.exec(select(Agent).where(Agent.id == aid)).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check quota
    quota = AgentQuota.get(aid, db)
    if not quota.has_message_quota(db):
        raise HTTPException(status_code=429, detail="Message quota exceeded")

    # Save input message
    input_message = ChatMessage(
        id=str(XID()),
        agent_id=aid,
        chat_id=request.chat_id,
        author_id=request.user_id,
        author_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
    )
    db.add(input_message)
    db.commit()

    try:
        # Execute agent
        image_urls = [
            attachment.url
            for attachment in (request.attachments or [])
            if attachment.type == ChatMessageAttachmentType.IMAGE
        ]
        agent_input = AgentMessageInput(text=request.message, images=image_urls)
        response_lines = execute_agent(aid, agent_input, f"{aid}-{request.chat_id}")

        # Create agent's response message
        response_message = ChatMessage(
            id=str(XID()),
            agent_id=aid,
            chat_id=request.chat_id,
            author_id=aid,
            author_type=AuthorType.AGENT,
            message="\n".join(response_lines),
            attachments=None,
        )
        db.add(response_message)

        # Update quota
        quota.add_message(db)
        db.commit()
        db.refresh(response_message)

        return response_message

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
