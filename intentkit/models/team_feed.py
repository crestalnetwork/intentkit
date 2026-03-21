from datetime import datetime
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base

T = TypeVar("T")


class TeamSubscriptionTable(Base):
    __tablename__: str = "team_subscriptions"

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TeamActivityFeedTable(Base):
    __tablename__: str = "team_activity_feed"
    __table_args__: Any = (
        Index("ix_team_activity_feed_team_created", "team_id", "created_at"),
    )

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TeamPostFeedTable(Base):
    __tablename__: str = "team_post_feed"
    __table_args__: Any = (
        Index("ix_team_post_feed_team_created", "team_id", "created_at"),
    )

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    post_id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TeamSubscription(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    team_id: str
    agent_id: str
    subscribed_at: datetime


class TeamFeedPage(BaseModel, Generic[T]):
    items: list[T] = PydanticField(default_factory=list)
    next_cursor: str | None = None
