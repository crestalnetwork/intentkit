from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session

logger = logging.getLogger(__name__)


class AgentToolDataTable(Base):
    """Database table model for storing tool-specific data for agents."""

    __tablename__: str = "agent_tool_data"

    agent_id: Mapped[str] = mapped_column(String, primary_key=True)
    tool: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class AgentToolDataCreate(BaseModel):
    """Base model for creating agent tool data records."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    agent_id: Annotated[str, Field(description="ID of the agent this data belongs to")]
    tool: Annotated[str, Field(description="Name of the tool this data is for")]
    key: Annotated[str, Field(description="Key for this specific piece of data")]
    data: Annotated[dict[str, Any], Field(description="JSON data stored for this key")]

    async def save(self) -> AgentToolData:
        """Save or update tool data.

        Returns:
            AgentToolData: The saved agent tool data instance

        Raises:
            Exception: If the total size would exceed the 10MB limit
        """
        # Calculate the size of the data
        data_size = len(json.dumps(self.data).encode("utf-8"))

        async with get_session() as db:
            # Check current total size for this agent
            current_total = await AgentToolData.total_size(self.agent_id)

            record = await db.scalar(
                select(AgentToolDataTable).where(
                    AgentToolDataTable.agent_id == self.agent_id,
                    AgentToolDataTable.tool == self.tool,
                    AgentToolDataTable.key == self.key,
                )
            )

            # Calculate new total size
            if record:
                # Update existing record - subtract old size, add new size
                new_total = current_total - record.size + data_size
            else:
                # Create new record - add new size
                new_total = current_total + data_size

            # Check if new total would exceed limit (10MB = 10 * 1024 * 1024 bytes)
            if new_total > 10 * 1024 * 1024:
                raise ValueError(
                    f"Total size would exceed 10MB limit. Current: {current_total}, New: {new_total}"
                )

            if record:
                # Update existing record
                record.data = self.data
                record.size = data_size
            else:
                # Create new record
                record = AgentToolDataTable(
                    agent_id=self.agent_id,
                    tool=self.tool,
                    key=self.key,
                    data=self.data,
                    size=data_size,
                )

            db.add(record)
            await db.commit()
            await db.refresh(record)
            return AgentToolData.model_validate(record)


class AgentToolData(AgentToolDataCreate):
    """Model for storing tool-specific data for agents.

    This model uses a composite primary key of (agent_id, tool, key) to store
    tool-specific data for agents in a flexible way.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    size: Annotated[int, Field(description="Size of the data in bytes")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this data was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this data was updated")
    ]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def total_size(cls, agent_id: str) -> int:
        """Calculate the total size of all tool data for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            int: Total size in bytes of all tool data for the agent
        """
        async with get_session() as db:
            result = await db.scalar(
                select(func.coalesce(func.sum(AgentToolDataTable.size), 0)).where(
                    AgentToolDataTable.agent_id == agent_id
                )
            )
            return result or 0

    @classmethod
    async def get(cls, agent_id: str, tool: str, key: str) -> dict[str, Any] | None:
        """Get tool data for an agent.

        Args:
            agent_id: ID of the agent
            tool: Name of the tool
            key: Data key

        Returns:
            Dictionary containing the tool data if found, None otherwise
        """
        async with get_session() as db:
            result = await db.scalar(
                select(AgentToolDataTable).where(
                    AgentToolDataTable.agent_id == agent_id,
                    AgentToolDataTable.tool == tool,
                    AgentToolDataTable.key == key,
                )
            )
            return result.data if result else None

    @classmethod
    async def delete(cls, agent_id: str, tool: str, key: str) -> None:
        """Delete tool data for an agent.

        Args:
            agent_id: ID of the agent
            tool: Name of the tool
            key: Data key
        """
        async with get_session() as db:
            _ = await db.execute(
                delete(AgentToolDataTable).where(
                    AgentToolDataTable.agent_id == agent_id,
                    AgentToolDataTable.tool == tool,
                    AgentToolDataTable.key == key,
                )
            )
            await db.commit()

    @classmethod
    async def clean_data(cls, agent_id: str):
        """Clean all tool data for an agent.

        Args:
            agent_id: ID of the agent
        """
        async with get_session() as db:
            _ = await db.execute(
                delete(AgentToolDataTable).where(
                    AgentToolDataTable.agent_id == agent_id
                )
            )
            await db.commit()


class ChatToolDataTable(Base):
    """Database table model for storing tool-specific data for chats."""

    __tablename__: str = "chat_tool_data"

    chat_id: Mapped[str] = mapped_column(String, primary_key=True)
    tool: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class ChatToolDataCreate(BaseModel):
    """Base model for creating chat tool data records."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    chat_id: Annotated[str, Field(description="ID of the chat this data belongs to")]
    tool: Annotated[str, Field(description="Name of the tool this data is for")]
    key: Annotated[str, Field(description="Key for this specific piece of data")]
    agent_id: Annotated[str, Field(description="ID of the agent that owns this chat")]
    data: Annotated[dict[str, Any], Field(description="JSON data stored for this key")]

    async def save(self) -> ChatToolData:
        """Save or update tool data.

        Returns:
            ChatToolData: The saved chat tool data instance
        """
        async with get_session() as db:
            record = await db.scalar(
                select(ChatToolDataTable).where(
                    ChatToolDataTable.chat_id == self.chat_id,
                    ChatToolDataTable.tool == self.tool,
                    ChatToolDataTable.key == self.key,
                )
            )

            if record:
                # Update existing record
                record.data = self.data
                record.agent_id = self.agent_id
            else:
                # Create new record
                record = ChatToolDataTable(**self.model_dump())
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return ChatToolData.model_validate(record)


class ChatToolData(ChatToolDataCreate):
    """Model for storing tool-specific data for chats.

    This model uses a composite primary key of (chat_id, tool, key) to store
    tool-specific data for chats in a flexible way. It also includes agent_id
    as a required field for tracking ownership.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this data was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this data was updated")
    ]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def get(cls, chat_id: str, tool: str, key: str) -> dict[str, Any] | None:
        """Get tool data for a chat.

        Args:
            chat_id: ID of the chat
            tool: Name of the tool
            key: Data key

        Returns:
            Dictionary containing the tool data if found, None otherwise
        """
        async with get_session() as db:
            record = await db.scalar(
                select(ChatToolDataTable).where(
                    ChatToolDataTable.chat_id == chat_id,
                    ChatToolDataTable.tool == tool,
                    ChatToolDataTable.key == key,
                )
            )
        return record.data if record else None

    @classmethod
    async def clean_data(
        cls,
        agent_id: str,
        chat_id: Annotated[
            str,
            Field(
                default="",
                description="Optional ID of the chat. If provided, only cleans data for that chat.",
            ),
        ],
    ):
        """Clean all tool data for a chat or agent.

        Args:
            agent_id: ID of the agent
            chat_id: Optional ID of the chat. If provided, only cleans data for that chat.
                     If empty, cleans all data for the agent.
        """
        async with get_session() as db:
            if chat_id and chat_id != "":
                _ = await db.execute(
                    delete(ChatToolDataTable).where(
                        ChatToolDataTable.agent_id == agent_id,
                        ChatToolDataTable.chat_id == chat_id,
                    )
                )
            else:
                _ = await db.execute(
                    delete(ChatToolDataTable).where(
                        ChatToolDataTable.agent_id == agent_id
                    )
                )
            await db.commit()
