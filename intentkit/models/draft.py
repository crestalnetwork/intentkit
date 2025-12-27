from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from epyxid import XID
from fastapi import status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Index, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.models.agent import (
    AgentUserInput,
    AgentUserInputColumns,
)
from intentkit.models.base import Base
from intentkit.models.db import get_session
from intentkit.utils.error import IntentKitAPIError


class AgentState(str, Enum):
    """Agent state."""

    PRIVATE = "private"
    PUBLIC = "public"
    CITIZEN = "citizen"


class AgentExtra(BaseModel):
    """Agent extra data in AgentUpdate."""

    state: AgentState = Field(default=AgentState.PRIVATE, description="Agent state")
    draft_id: str = Field(description="Draft ID")
    project_id: str | None = Field(
        default=None, description="Project ID, forward compatible"
    )
    request_id: str | None = Field(
        default=None, description="Request ID, forward compatible"
    )
    create_tx_id: str | None = Field(
        default=None, description="Transaction hash used when the agent was created"
    )


class AgentDraftTable(Base, AgentUserInputColumns):
    """Agent table db model."""

    __tablename__ = "agent_drafts"

    # Indexes for optimal query performance
    __table_args__ = (
        # Index for queries filtering by agent_id and owner (most common pattern)
        Index("idx_agent_drafts_agent_owner", "agent_id", "owner"),
        # Index for queries ordering by created_at (for latest draft queries)
        Index("idx_agent_drafts_created_at", "created_at"),
        # Composite index for agent_id, owner, and created_at (covers all common query patterns)
        Index(
            "idx_agent_drafts_agent_owner_created", "agent_id", "owner", "created_at"
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        comment="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    agent_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Agent id",
    )
    owner: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Owner identifier of the agent, used for access control",
    )
    team_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Team identifier of the agent, used for access control",
    )
    version: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Version hash of the agent",
    )
    project_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Project ID, forward compatible",
    )
    last_draft_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="ID of the last draft that was deployed",
    )
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent was deployed",
    )
    # auto timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the agent was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        comment="Timestamp when the agent was last updated",
    )


class AgentDraft(AgentUserInput):
    """Agent draft model."""

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the draft",
        ),
    ]
    agent_id: Annotated[
        str,
        Field(
            description="Agent id",
        ),
    ]
    owner: Annotated[
        str | None,
        Field(
            default=None,
            description="Owner identifier of the agent, used for access control",
            max_length=50,
        ),
    ]
    team_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Team identifier of the agent, used for access control",
            max_length=50,
        ),
    ]
    version: Annotated[
        str | None,
        Field(
            default=None,
            description="Version hash of the agent",
        ),
    ]
    project_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Project ID, forward compatible",
        ),
    ]
    last_draft_id: Annotated[
        str | None,
        Field(
            default=None,
            description="ID of the last draft that was deployed",
        ),
    ]
    deployed_at: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Timestamp when the agent was deployed",
        ),
    ]
    # auto timestamp
    created_at: Annotated[
        datetime,
        Field(
            description="Timestamp when the agent was created, will ignore when importing"
        ),
    ]
    updated_at: Annotated[
        datetime,
        Field(
            description="Timestamp when the agent was last updated, will ignore when importing"
        ),
    ]

    @staticmethod
    async def exist(agent_id: str, user_id: str | None = None) -> None:
        """Check if an agent exists in the draft table.

        Args:
            agent_id: The agent ID to check
            user_id: Optional user ID to check ownership

        Raises:
            IntentKitAPIError: 404 if agent not found, 403 if user doesn't own the agent
        """
        async with get_session() as session:
            query = (
                select(AgentDraftTable)
                .where(AgentDraftTable.agent_id == agent_id)
                .limit(1)
            )
            result = await session.execute(query)
            draft = result.scalar_one_or_none()

            if not draft:
                raise IntentKitAPIError(
                    status.HTTP_404_NOT_FOUND,
                    "AgentNotFound",
                    f"Agent {agent_id} not found",
                )

            if user_id is not None and draft.owner != user_id:
                raise IntentKitAPIError(
                    status.HTTP_403_FORBIDDEN,
                    "AgentForbidden",
                    "Agent does not belong to user",
                )
