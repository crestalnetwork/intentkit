from datetime import datetime
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base


class AgentActivityBase(BaseModel):
    agent_id: Annotated[str, PydanticField(description="ID of the agent")]
    agent_name: Annotated[
        str | None, PydanticField(description="Name of the agent")
    ] = None
    agent_picture: Annotated[
        str | None, PydanticField(description="Picture URL of the agent")
    ] = None
    text: Annotated[str, PydanticField(description="Content of the activity")]
    images: Annotated[
        list[str] | None, PydanticField(description="List of image URLs")
    ] = None
    video: Annotated[str | None, PydanticField(description="Video URL")] = None
    post_id: Annotated[str | None, PydanticField(description="Related post ID")] = None


class AgentActivityCreate(AgentActivityBase):
    pass


class AgentActivity(AgentActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: Annotated[str, PydanticField(description="Unique identifier for the activity")]
    created_at: Annotated[datetime, PydanticField(description="Timestamp when created")]


class AgentActivityTable(Base):
    __tablename__ = "agent_activities"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(XID()),
        comment="Unique identifier for the activity",
    )
    agent_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="ID of the agent"
    )
    agent_name: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Name of the agent"
    )
    agent_picture: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Picture URL of the agent"
    )
    text: Mapped[str] = mapped_column(String, nullable=False, comment="Content")
    images: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True, comment="List of image URLs"
    )
    video: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Video URL"
    )
    post_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True, comment="Related post ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when created",
    )
