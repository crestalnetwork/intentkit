import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional, Type, TypeVar

from intentkit.models.base import Base
from intentkit.models.credit import CreditAccount
from intentkit.models.db import get_session
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Index, Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# TypeVar for User model constraint
UserModelType = TypeVar("UserModelType", bound="User")
UserTableType = TypeVar("UserTableType", bound="UserTable")


class UserRegistry:
    """Registry for extended model classes."""

    def __init__(self):
        self._user_table_class: Optional[Type[UserTableType]] = None
        self._user_model_class: Optional[Type[UserModelType]] = None

    def register_user_table(self, user_table_class: Type[UserTableType]) -> None:
        """Register extended UserTable class.

        Args:
            user_table_class: A class that inherits from UserTable
        """
        self._user_table_class = user_table_class

    def get_user_table_class(self) -> Type[UserTableType]:
        """Get registered UserTable class or default."""
        return self._user_table_class or UserTable

    def register_user_model(self, user_model_class: Type[UserModelType]) -> None:
        """Register extended UserModel class.

        Args:
            user_model_class: A class that inherits from User
        """
        self._user_model_class = user_model_class

    def get_user_model_class(self) -> Type[UserModelType]:
        """Get registered UserModel class or default."""
        return self._user_model_class or User


# Global registry instance
user_model_registry = UserRegistry()


class UserTable(Base):
    """User database table model."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_x_username", "x_username"),
        Index("ix_users_telegram_username", "telegram_username"),
    )

    id = Column(
        String,
        primary_key=True,
    )
    nft_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    email = Column(
        String,
        nullable=True,
    )
    x_username = Column(
        String,
        nullable=True,
    )
    github_username = Column(
        String,
        nullable=True,
    )
    telegram_username = Column(
        String,
        nullable=True,
    )
    extra = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
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


class UserUpdate(BaseModel):
    """User update model without id and timestamps."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    nft_count: Annotated[
        int, Field(default=0, description="Number of NFTs owned by the user")
    ]
    email: Annotated[Optional[str], Field(None, description="User's email address")]
    x_username: Annotated[
        Optional[str], Field(None, description="User's X (Twitter) username")
    ]
    github_username: Annotated[
        Optional[str], Field(None, description="User's GitHub username")
    ]
    telegram_username: Annotated[
        Optional[str], Field(None, description="User's Telegram username")
    ]
    extra: Annotated[
        Optional[dict], Field(None, description="Additional user information")
    ]

    async def _update_quota_for_nft_count(
        self, db: AsyncSession, id: str, new_nft_count: int
    ) -> None:
        """Update user's daily quota based on NFT count.

        Args:
            db: Database session
            id: User ID
            new_nft_count: Current NFT count
        """
        # Generate upstream_tx_id
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        upstream_tx_id = f"nft_{id}_{timestamp}"

        # Calculate new quota values based on nft_count
        free_quota = Decimal(480 + 48 * new_nft_count)
        refill_amount = Decimal(20 + 2 * new_nft_count)
        note = f"NFT count changed to {new_nft_count}"

        # Update daily quota
        logger.info(
            f"Updating daily quota for user {id} due to NFT count change to {new_nft_count}"
        )
        await CreditAccount.update_daily_quota(
            db,
            id,
            free_quota=free_quota,
            refill_amount=refill_amount,
            upstream_tx_id=upstream_tx_id,
            note=note,
        )

    async def patch(self, id: str) -> "User":
        """Update only the provided fields of a user in the database.
        If the user doesn't exist, create a new one with the provided ID and fields.
        If nft_count changes, update the daily quota accordingly.

        Args:
            id: ID of the user to update or create

        Returns:
            Updated or newly created User model
        """
        user_model_class = user_model_registry.get_user_model_class()
        user_table_class = user_model_registry.get_user_table_class()
        async with get_session() as db:
            db_user = await db.get(user_table_class, id)
            old_nft_count = 0  # Default for new users

            if not db_user:
                # Create new user if it doesn't exist
                db_user = user_table_class(id=id)
                db.add(db_user)
            else:
                old_nft_count = db_user.nft_count

            # Update only the fields that were provided
            update_data = self.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_user, key, value)

            # Check if nft_count has changed and is in the update data
            if "nft_count" in update_data and old_nft_count != update_data["nft_count"]:
                await self._update_quota_for_nft_count(db, id, update_data["nft_count"])

            await db.commit()
            await db.refresh(db_user)

            return user_model_class.model_validate(db_user)

    async def put(self, id: str) -> "User":
        """Replace all fields of a user in the database with the provided values.
        If the user doesn't exist, create a new one with the provided ID and fields.
        If nft_count changes, update the daily quota accordingly.

        Args:
            id: ID of the user to update or create

        Returns:
            Updated or newly created User model
        """
        user_model_class = user_model_registry.get_user_model_class()
        user_table_class = user_model_registry.get_user_table_class()
        async with get_session() as db:
            db_user = await db.get(user_table_class, id)
            old_nft_count = 0  # Default for new users

            if not db_user:
                # Create new user if it doesn't exist
                db_user = user_table_class(id=id)
                db.add(db_user)
            else:
                old_nft_count = db_user.nft_count

            # Replace all fields with the provided values
            for key, value in self.model_dump().items():
                setattr(db_user, key, value)

            # Check if nft_count has changed
            if old_nft_count != self.nft_count:
                await self._update_quota_for_nft_count(db, id, self.nft_count)

            await db.commit()
            await db.refresh(db_user)

            return user_model_class.model_validate(db_user)


class User(UserUpdate):
    """User model with all fields including id and timestamps."""

    id: Annotated[
        str,
        Field(description="Unique identifier for the user"),
    ]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this user was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this user was last updated")
    ]

    @classmethod
    async def get(cls, user_id: str) -> Optional["User"]:
        """Get a user by ID.

        Args:
            user_id: ID of the user to get

        Returns:
            User model or None if not found
        """
        async with get_session() as session:
            return await cls.get_in_session(session, user_id)

    @classmethod
    async def get_in_session(
        cls, session: AsyncSession, user_id: str
    ) -> Optional["User"]:
        """Get a user by ID using the provided session.

        Args:
            session: Database session
            user_id: ID of the user to get

        Returns:
            User model or None if not found
        """
        user_table_class = user_model_registry.get_user_table_class()
        result = await session.execute(
            select(user_table_class).where(user_table_class.id == user_id)
        )
        user = result.scalars().first()
        if user is None:
            return None
        return cls.model_validate(user)
