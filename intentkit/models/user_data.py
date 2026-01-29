"""User data model for storing secure key-value data for users."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session

logger = logging.getLogger(__name__)


class UserDataTable(Base):
    """Database model for storing key-value data for users.

    This model uses a composite primary key of (user_id, key) to store
    user-specific data in a flexible way.

    Attributes:
        user_id: ID of the user this data belongs to
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "user_data"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
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


class UserData(BaseModel):
    """Model for storing key-value data for users.

    This model uses a composite primary key of (user_id, key) to store
    user-specific data in a flexible way.

    Attributes:
        user_id: ID of the user this data belongs to
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: Annotated[
        str,
        PydanticField(description="ID of the user this data belongs to"),
    ]
    key: Annotated[
        str,
        PydanticField(description="Key for this specific piece of data"),
    ]
    data: Annotated[
        dict[str, Any] | None,
        PydanticField(default=None, description="JSON data stored for this key"),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when this data was created"),
    ] = PydanticField(default_factory=lambda: datetime.now(UTC))
    updated_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when this data was last updated"),
    ] = PydanticField(default_factory=lambda: datetime.now(UTC))

    @classmethod
    async def get(cls, user_id: str, key: str) -> "UserData | None":
        """Get user data by user_id and key.

        Args:
            user_id: ID of the user
            key: Data key

        Returns:
            UserData if found, None otherwise
        """
        async with get_session() as db:
            item = await db.scalar(
                select(UserDataTable).where(
                    UserDataTable.user_id == user_id,
                    UserDataTable.key == key,
                )
            )
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update user data."""
        async with get_session() as db:
            existing = await db.scalar(
                select(UserDataTable).where(
                    UserDataTable.user_id == self.user_id,
                    UserDataTable.key == self.key,
                )
            )

            if existing:
                # Update existing record
                existing.data = self.data
                db.add(existing)
            else:
                # Create new record
                user_data = UserDataTable(
                    user_id=self.user_id,
                    key=self.key,
                    data=self.data,
                )
                db.add(user_data)

            await db.commit()

    @classmethod
    async def delete(cls, user_id: str, key: str) -> bool:
        """Delete user data by user_id and key.

        Args:
            user_id: ID of the user
            key: Data key

        Returns:
            True if deleted, False if not found
        """
        async with get_session() as db:
            existing = await db.scalar(
                select(UserDataTable).where(
                    UserDataTable.user_id == user_id,
                    UserDataTable.key == key,
                )
            )
            if existing:
                await db.delete(existing)
                await db.commit()
                return True
            return False
