"""Shared chat models and utility functions used by both local and team APIs."""

import asyncio
import logging
from typing import Annotated, ClassVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from intentkit.config.db import get_session
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageTable,
)
from intentkit.models.llm import create_llm_model
from intentkit.models.llm_picker import pick_summarize_model

logger = logging.getLogger(__name__)

SUMMARY_TITLE_SYSTEM_PROMPT = (
    "Generate a concise chat title in the same language as the conversation. "
    "Return title text only, with no quotes or explanations."
)


# =============================================================================
# Response Models
# =============================================================================


class ChatMessagesResponse(BaseModel):
    """Response model for chat messages with pagination."""

    data: list[ChatMessage]
    has_more: bool = False
    next_cursor: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {"data": [], "has_more": False, "next_cursor": None}
        },
    )


# =============================================================================
# Request Models
# =============================================================================


class ChatUpdateRequest(BaseModel):
    """Request model for updating a chat thread."""

    summary: Annotated[
        str,
        Field(
            ...,
            description="Updated summary for the chat thread",
            examples=["Updated chat summary"],
            max_length=500,
        ),
    ]

    model_config: ClassVar[ConfigDict] = ConfigDict(
        json_schema_extra={"example": {"summary": "Updated chat summary"}},
    )


class LocalChatCreateRequest(BaseModel):
    """Request model for creating a local chat thread."""

    chat_id: Annotated[
        str | None,
        Field(
            None,
            description="Optional client-provided chat id (reserved, currently ignored)",
        ),
    ] = None
    first_message: Annotated[
        str | None,
        Field(
            None,
            description="Optional first user message used to generate chat title",
            max_length=65535,
        ),
    ] = None


class LocalChatMessageRequest(BaseModel):
    """Request model for local chat messages.

    This model represents the request body for creating a new chat message.
    Simplified for local single-user mode without user_id and app_id.
    """

    message: Annotated[
        str,
        Field(
            ...,
            description="Content of the message",
            examples=["Hello, how can you help me today?"],
            min_length=1,
            max_length=65535,
        ),
    ]
    stream: Annotated[
        bool | None,
        Field(
            None,
            description="Whether to stream the response",
        ),
    ]
    attachments: Annotated[
        list[ChatMessageAttachment] | None,
        Field(
            None,
            description="Optional list of attachments (links, images, or files)",
            examples=[[{"type": "link", "url": "https://example.com"}]],
        ),
    ]

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "message": "Hello, how can you help me today?",
                "attachments": [
                    {
                        "type": "link",
                        "url": "https://example.com",
                    }
                ],
            }
        },
    )


# =============================================================================
# Chat Summary Utilities
# =============================================================================


def _is_user_author_type(author_type: AuthorType) -> bool:
    return author_type == AuthorType.WEB


async def _count_user_messages(agent_id: str, chat_id: str) -> int:
    async with get_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.author_type == AuthorType.WEB,
            )
        )
        return int(count or 0)


async def should_schedule_chat_summary(
    agent_id: str, chat_id: str, incoming_author_type: AuthorType
) -> bool:
    if not _is_user_author_type(incoming_author_type):
        return False
    previous_user_count = await _count_user_messages(agent_id, chat_id)
    return previous_user_count + 1 == 3


def _extract_model_response_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return str(content)


def _normalize_summary_title(title: str) -> str:
    normalized = " ".join(title.split())
    return normalized[:40]


async def _generate_summary_title(prompt_text: str) -> str:
    content = prompt_text.strip()
    if not content:
        return ""

    summarize_model = pick_summarize_model()
    llm = await create_llm_model(model_name=summarize_model, temperature=0.2)
    model = await llm.create_instance()
    response = await model.ainvoke(
        [
            SystemMessage(content=SUMMARY_TITLE_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
    )
    raw_title = _extract_model_response_text(response.content)
    return _normalize_summary_title(raw_title)


async def _load_first_three_round_transcript(agent_id: str, chat_id: str) -> str:
    async with get_session() as db:
        rows = await db.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
            )
            .order_by(ChatMessageTable.created_at)
            .limit(200)
        )
        messages = [ChatMessage.model_validate(row) for row in rows.all()]

    user_round_count = 0
    transcript_lines: list[str] = []
    for message in messages:
        if _is_user_author_type(message.author_type):
            user_round_count += 1
            if user_round_count > 3:
                break

        content = message.message.strip()
        if not content:
            continue

        if _is_user_author_type(message.author_type):
            role = "User"
        elif message.author_type == AuthorType.AGENT:
            role = "Assistant"
        elif message.author_type == AuthorType.SKILL:
            role = "Tool"
        else:
            role = "System"
        transcript_lines.append(f"{role}: {content}")

    return "\n".join(transcript_lines)


async def _generate_chat_summary_title(agent_id: str, chat_id: str) -> str:
    transcript = await _load_first_three_round_transcript(agent_id, chat_id)
    if not transcript:
        return ""

    return await _generate_summary_title(f"Conversation:\n{transcript}")


async def _update_chat_summary_title(agent_id: str, chat_id: str) -> None:
    chat = await Chat.get(chat_id)
    if not chat:
        logger.info(
            f"Skip chat summary title update because chat was not found: {chat_id}"
        )
        return
    if chat.agent_id != agent_id:
        return

    try:
        title = await _generate_chat_summary_title(agent_id, chat_id)
        if not title:
            return
        _ = await chat.update_summary(title)
    except Exception:
        logger.exception(
            f"Failed to generate chat summary title for chat {chat_id} of agent {agent_id}"
        )


def schedule_chat_summary_title_update(agent_id: str, chat_id: str) -> None:
    _ = asyncio.create_task(_update_chat_summary_title(agent_id, chat_id))


def should_summarize_first_message(first_message: str | None) -> bool:
    if not first_message:
        return False
    return len(first_message.encode("utf-8")) > 20


async def update_chat_summary_from_first_message(
    agent_id: str, chat_id: str, first_message: str
) -> None:
    chat = await Chat.get(chat_id)
    if not chat:
        logger.info(
            f"Skip chat summary title update because chat was not found: {chat_id}"
        )
        return
    if chat.agent_id != agent_id:
        return

    try:
        title = await _generate_summary_title(f"First user message:\n{first_message}")
        if not title:
            return
        _ = await chat.update_summary(title)
    except Exception:
        logger.exception(
            f"Failed to generate first-message summary title for chat {chat_id} of agent {agent_id}"
        )
