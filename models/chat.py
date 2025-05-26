from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, List, NotRequired, Optional, TypedDict

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    desc,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base
from models.db import get_session


class ChatMessageAttachmentType(str, Enum):
    """Type of chat message attachment."""

    LINK = "link"
    IMAGE = "image"
    FILE = "file"


class AuthorType(str, Enum):
    """Type of message author."""

    AGENT = "agent"
    TRIGGER = "trigger"
    SKILL = "skill"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    WEB = "web"
    SYSTEM = "system"


class ChatMessageAttachment(TypedDict):
    """Chat message attachment model.

    An attachment can be a link, image, or file that is associated with a chat message.
    """

    type: Annotated[
        ChatMessageAttachmentType,
        Field(
            ...,
            description="Type of the attachment (link, image, or file)",
            examples=["link"],
        ),
    ]
    url: Annotated[
        str,
        Field(
            ...,
            description="URL of the attachment",
            examples=["https://example.com/image.jpg"],
        ),
    ]


class ChatMessageSkillCall(TypedDict):
    """TypedDict for skill call details."""

    id: NotRequired[str]
    name: str
    parameters: dict
    success: bool
    response: NotRequired[
        str
    ]  # Optional response from the skill call, trimmed to 100 characters
    error_message: NotRequired[str]  # Optional error message from the skill call
    credit_event_id: NotRequired[str]  # ID of the credit event for this skill call
    credit_cost: NotRequired[Decimal]  # Credit cost for the skill call


class ChatMessageRequest(BaseModel):
    """Request model for chat messages.

    This model represents the request body for creating a new chat message.
    It contains the necessary fields to identify the chat context, user,
    and message content, along with optional attachments.
    """

    chat_id: Annotated[
        str,
        Field(
            ...,
            description="Unique identifier for the chat thread",
            examples=["chat-123"],
            min_length=1,
        ),
    ]
    user_id: Annotated[
        str,
        Field(
            ...,
            description="Unique identifier of the user sending the message",
            examples=["user-456"],
            min_length=1,
        ),
    ]
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
    attachments: Annotated[
        Optional[List[ChatMessageAttachment]],
        Field(
            None,
            description="Optional list of attachments (links, images, or files)",
            examples=[[{"type": "link", "url": "https://example.com"}]],
        ),
    ]

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "chat_id": "chat-123",
                "user_id": "user-456",
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


class ChatMessageTable(Base):
    """Chat message database table model."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_chat_id", "chat_id"),)

    id = Column(
        String,
        primary_key=True,
    )
    agent_id = Column(
        String,
        nullable=False,
    )
    chat_id = Column(
        String,
        nullable=False,
    )
    user_id = Column(
        String,
        nullable=True,
    )
    author_id = Column(
        String,
        nullable=False,
    )
    author_type = Column(
        String,
        nullable=False,
    )
    model = Column(
        String,
        nullable=True,
    )
    thread_type = Column(
        String,
        nullable=True,
    )
    reply_to = Column(
        String,
        nullable=True,
    )
    message = Column(
        String,
        nullable=False,
    )
    attachments = Column(
        JSONB,
        nullable=True,
    )
    skill_calls = Column(
        JSONB,
        nullable=True,
    )
    input_tokens = Column(
        Integer,
        default=0,
    )
    output_tokens = Column(
        Integer,
        default=0,
    )
    time_cost = Column(
        Float,
        default=0,
    )
    credit_event_id = Column(
        String,
        nullable=True,
    )
    credit_cost = Column(
        Numeric(22, 4),
        nullable=True,
    )
    cold_start_cost = Column(
        Float,
        default=0,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChatMessageCreate(BaseModel):
    """Base model for creating chat messages with fields needed for creation."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the chat message",
        ),
    ]
    agent_id: Annotated[
        str, Field(description="ID of the agent this message belongs to")
    ]
    chat_id: Annotated[str, Field(description="ID of the chat this message belongs to")]
    user_id: Annotated[
        Optional[str],
        Field(description="ID of the user this message belongs to or reply to"),
    ]
    author_id: Annotated[str, Field(description="ID of the message author")]
    author_type: Annotated[AuthorType, Field(description="Type of the message author")]
    model: Annotated[
        Optional[str], Field(None, description="LLM model used if applicable")
    ]
    thread_type: Annotated[
        Optional[AuthorType],
        Field(None, description="Author Type of the message thread start"),
    ]
    reply_to: Annotated[
        Optional[str],
        Field(None, description="ID of the message this message is a reply to"),
    ]
    message: Annotated[str, Field(description="Content of the message")]
    attachments: Annotated[
        Optional[List[ChatMessageAttachment]],
        Field(None, description="List of attachments in the message"),
    ]
    skill_calls: Annotated[
        Optional[List[ChatMessageSkillCall]],
        Field(None, description="Skill call details"),
    ]
    input_tokens: Annotated[
        int, Field(0, description="Number of tokens in the input message")
    ]
    output_tokens: Annotated[
        int, Field(0, description="Number of tokens in the output message")
    ]
    time_cost: Annotated[
        float, Field(0.0, description="Time cost for the message in seconds")
    ]
    credit_event_id: Annotated[
        Optional[str],
        Field(None, description="ID of the credit event for this message"),
    ]
    credit_cost: Annotated[
        Optional[Decimal],
        Field(None, description="Credit cost for the message in credits"),
    ]
    cold_start_cost: Annotated[
        float,
        Field(0.0, description="Cost for the cold start of the message in seconds"),
    ]

    async def save_in_session(self, db: AsyncSession) -> "ChatMessage":
        """Save the chat message to the database.

        Returns:
            ChatMessage: The saved chat message with all fields populated
        """
        message_record = ChatMessageTable(**self.model_dump(mode="json"))
        db.add(message_record)
        await db.flush()
        await db.refresh(message_record)
        return ChatMessage.model_validate(message_record)

    async def save(self) -> "ChatMessage":
        """Save the chat message to the database.

        Returns:
            ChatMessage: The saved chat message with all fields populated
        """
        async with get_session() as db:
            resp = await self.save_in_session(db)
            await db.commit()
            return resp


class ChatMessage(ChatMessageCreate):
    """Chat message model with all fields including server-generated ones."""

    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
        from_attributes=True,
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this message was created")
    ]

    def __str__(self):
        resp = ""
        if self.skill_calls:
            for call in self.skill_calls:
                resp += f"{call['name']} {call['parameters']}: {call['response'] if call['success'] else call['error_message']}\n"
            resp += "\n"
        resp += self.message
        return resp

    @classmethod
    async def get(cls, chat_id: str) -> Optional["ChatMessage"]:
        async with get_session() as db:
            raw = await db.get(ChatMessageTable, chat_id)
            if raw:
                return ChatMessage.model_validate(raw)
            return None


class ChatTable(Base):
    """Chat database table model."""

    __tablename__ = "chats"
    __table_args__ = (Index("ix_chats_agent_user", "agent_id", "user_id"),)

    id = Column(
        String,
        primary_key=True,
    )
    agent_id = Column(
        String,
        nullable=False,
    )
    user_id = Column(
        String,
        nullable=False,
    )
    summary = Column(
        String,
        default="",
    )
    rounds = Column(
        Integer,
        default=0,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ChatCreate(BaseModel):
    """Base model for creating chats with fields needed for creation."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the chat",
        ),
    ]
    agent_id: Annotated[str, Field(description="ID of the agent this chat belongs to")]
    user_id: Annotated[str, Field(description="User ID of the chat")]
    summary: Annotated[str, Field("", description="Summary of the chat")]
    rounds: Annotated[int, Field(0, description="Number of rounds in the chat")]

    async def save(self) -> "Chat":
        """Create a new chat in the database.

        Returns:
            Chat: The saved chat with all fields populated
        """
        # Set timestamps
        chat_record = ChatTable(**self.model_dump(exclude_unset=True))

        async with get_session() as db:
            db.add(chat_record)
            await db.commit()
            await db.refresh(chat_record)

            # Create and return a full Chat instance
            return Chat.model_validate(chat_record)


class Chat(ChatCreate):
    """Chat model with all fields including server-generated ones."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this chat was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this chat was updated")
    ]

    @classmethod
    async def get(cls, id: str) -> Optional["Chat"]:
        """Get a chat by its ID.

        Args:
            id: ID of the chat to get

        Returns:
            Chat if found, None otherwise
        """
        async with get_session() as db:
            chat_record = await db.get(ChatTable, id)
            if chat_record:
                return cls.model_validate(chat_record)
            return None

    async def delete(self):
        """Delete the chat from the database."""
        async with get_session() as db:
            chat_record = await db.get(ChatTable, self.id)
            if chat_record:
                await db.delete(chat_record)
                await db.commit()

    async def add_round(self):
        """Increment the number of rounds in the chat on the database server.

        Uses a direct SQL UPDATE statement to increment the rounds counter
        on the server side, avoiding potential race conditions.
        """
        async with get_session() as db:
            stmt = (
                update(ChatTable)
                .where(ChatTable.id == self.id)
                .values(rounds=ChatTable.rounds + 1)
            )
            await db.execute(stmt)
            await db.commit()

            # Update local object
            self.rounds += 1

    async def update_summary(self, summary: str) -> "Chat":
        """Update the chat summary in the database.

        Uses a direct SQL UPDATE statement to set the summary field.

        Args:
            summary: New summary text for the chat

        Returns:
            Chat: The updated chat instance
        """
        async with get_session() as db:
            stmt = (
                update(ChatTable).where(ChatTable.id == self.id).values(summary=summary)
            )
            await db.execute(stmt)
            await db.commit()

            # Update local object
            self.summary = summary
            return self

    @classmethod
    async def get_by_agent_user(cls, agent_id: str, user_id: str) -> List["Chat"]:
        """Get all chats for a specific agent and user.

        Args:
            agent_id: ID of the agent
            user_id: ID of the user

        Returns:
            List of chats
        """
        async with get_session() as db:
            results = await db.scalars(
                select(ChatTable)
                .order_by(desc(ChatTable.updated_at))
                .limit(10)
                .where(ChatTable.agent_id == agent_id, ChatTable.user_id == user_id)
            )

            return [cls.model_validate(chat) for chat in results]
