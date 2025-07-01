"""Conversation models for agent generator.

This module provides models for tracking conversation history and projects
related to agent generation sessions.
"""

from datetime import datetime
from typing import Annotated, List, Optional

from epyxid import XID
from intentkit.models.base import Base
from intentkit.models.db import get_session
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
    desc,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.ext.asyncio import AsyncSession


class ConversationProjectTable(Base):
    """Conversation project database table model."""

    __tablename__ = "generator_conversation_projects"
    __table_args__ = (
        Index("ix_generator_conversation_projects_user_id", "user_id"),
        Index("ix_generator_conversation_projects_created_at", "created_at"),
    )

    id = Column(
        String,
        primary_key=True,
    )
    user_id = Column(
        String,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_activity = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConversationMessageTable(Base):
    """Conversation message database table model."""

    __tablename__ = "generator_conversation_messages"
    __table_args__ = (
        Index("ix_generator_conversation_messages_project_id", "project_id"),
        Index("ix_generator_conversation_messages_created_at", "created_at"),
    )

    id = Column(
        String,
        primary_key=True,
    )
    project_id = Column(
        String,
        nullable=False,
    )
    role = Column(
        String,
        nullable=False,
    )
    content = Column(
        Text,
        nullable=False,
    )
    message_metadata = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConversationProjectCreate(BaseModel):
    """Base model for creating conversation projects."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the conversation project",
        ),
    ]
    user_id: Annotated[
        Optional[str],
        Field(None, description="User ID associated with this project"),
    ]

    async def save_in_session(self, db: AsyncSession) -> "ConversationProject":
        """Save the conversation project in the given database session."""
        db_project = ConversationProjectTable(
            id=self.id,
            user_id=self.user_id,
        )
        db.add(db_project)
        await db.flush()
        await db.refresh(db_project)
        return ConversationProject.model_validate(db_project)

    async def save(self) -> "ConversationProject":
        """Save the conversation project to the database."""
        async with get_session() as db:
            result = await self.save_in_session(db)
            await db.commit()
            return result


class ConversationProject(ConversationProjectCreate):
    """Conversation project model with all fields including server-generated ones."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this project was created")
    ]
    last_activity: Annotated[
        datetime, Field(description="Timestamp of last activity in this project")
    ]

    @classmethod
    async def get(cls, project_id: str) -> Optional["ConversationProject"]:
        """Get a conversation project by ID."""
        async with get_session() as db:
            result = await db.execute(
                select(ConversationProjectTable).where(
                    ConversationProjectTable.id == project_id
                )
            )
            project = result.scalar_one_or_none()
            if project:
                return cls.model_validate(project)
            return None

    async def update_activity(self) -> "ConversationProject":
        """Update the last activity timestamp for this project."""
        async with get_session() as db:
            from sqlalchemy import update

            await db.execute(
                update(ConversationProjectTable)
                .where(ConversationProjectTable.id == self.id)
                .values(last_activity=func.now())
            )
            await db.commit()
            # Refresh the object
            result = await db.execute(
                select(ConversationProjectTable).where(
                    ConversationProjectTable.id == self.id
                )
            )
            project = result.scalar_one()
            return ConversationProject.model_validate(project)

    @classmethod
    async def get_by_user(
        cls, user_id: Optional[str] = None, limit: int = 50
    ) -> List["ConversationProject"]:
        """Get conversation projects by user ID."""
        async with get_session() as db:
            query = select(ConversationProjectTable).order_by(
                desc(ConversationProjectTable.last_activity)
            )

            if user_id is not None:
                query = query.where(ConversationProjectTable.user_id == user_id)

            query = query.limit(limit)

            result = await db.execute(query)
            projects = result.scalars().all()
            return [cls.model_validate(project) for project in projects]


class ConversationMessageCreate(BaseModel):
    """Base model for creating conversation messages."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the conversation message",
        ),
    ]
    project_id: Annotated[str, Field(description="Project ID this message belongs to")]
    role: Annotated[str, Field(description="Role of the message sender")]
    content: Annotated[str, Field(description="Content of the message")]
    message_metadata: Annotated[
        Optional[dict],
        Field(None, description="Additional metadata for the message"),
    ]

    async def save_in_session(self, db: AsyncSession) -> "ConversationMessage":
        """Save the conversation message in the given database session."""
        db_message = ConversationMessageTable(
            id=self.id,
            project_id=self.project_id,
            role=self.role,
            content=self.content,
            message_metadata=self.message_metadata,
        )
        db.add(db_message)
        await db.flush()
        await db.refresh(db_message)
        return ConversationMessage.model_validate(db_message)

    async def save(self) -> "ConversationMessage":
        """Save the conversation message to the database."""
        async with get_session() as db:
            result = await self.save_in_session(db)
            await db.commit()
            return result


class ConversationMessage(ConversationMessageCreate):
    """Conversation message model with all fields including server-generated ones."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this message was created")
    ]

    @classmethod
    async def get_by_project(
        cls, project_id: str, user_id: Optional[str] = None
    ) -> List["ConversationMessage"]:
        """Get conversation messages for a project."""
        async with get_session() as db:
            # First check if project exists and user has access
            project_query = select(ConversationProjectTable).where(
                ConversationProjectTable.id == project_id
            )
            if user_id is not None:
                project_query = project_query.where(
                    ConversationProjectTable.user_id == user_id
                )

            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()

            if not project:
                return []

            # Get messages for the project
            messages_query = (
                select(ConversationMessageTable)
                .where(ConversationMessageTable.project_id == project_id)
                .order_by(ConversationMessageTable.created_at)
            )

            result = await db.execute(messages_query)
            messages = result.scalars().all()
            return [cls.model_validate(message) for message in messages]
