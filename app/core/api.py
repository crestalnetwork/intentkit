"""Core API Router.

This module provides the core API endpoints for agent execution and management.
"""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import AfterValidator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

from app.core.engine import execute_agent
from models.chat import ChatMessage

core_router = APIRouter(prefix="/core", tags=["core"])


@core_router.post("/execute", response_model=list[ChatMessage])
async def execute(
    message: Annotated[ChatMessage, AfterValidator(ChatMessage.model_validate)] = Body(
        ChatMessage,
        description="The chat message containing agent_id, chat_id and message content",
    ),
) -> list[ChatMessage]:
    """Execute an agent with the given input and return response lines.

    **Request Body:**
    * `message` - The chat message containing agent_id, chat_id and message content

    **Returns:**
    * `list[ChatMessage]` - Formatted response lines from agent execution

    **Raises:**
    * `HTTPException`:
        - 400: If input parameters are invalid
        - 404: If agent not found
        - 500: For other server-side errors
    """
    message.created_at = None
    # Validate input parameters
    if not message.agent_id or not message.agent_id.strip():
        raise HTTPException(status_code=400, detail="Agent ID cannot be empty")
    if not message.chat_id or not message.chat_id.strip():
        raise HTTPException(status_code=400, detail="Chat ID cannot be empty")
    if not message.message or not message.message.strip():
        raise HTTPException(status_code=400, detail="Message text cannot be empty")

    try:
        return await execute_agent(message)
    except NoResultFound:
        raise HTTPException(
            status_code=404, detail=f"Agent {message.agent_id} not found"
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
