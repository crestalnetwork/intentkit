from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base
from models.db import get_session


class AgentSkillDataTable(Base):
    """Database table model for storing skill-specific data for agents."""

    __tablename__ = "agent_skill_data"

    agent_id = Column(String, primary_key=True)
    skill = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    data = Column(JSONB, nullable=True)
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


class AgentSkillDataCreate(BaseModel):
    """Base model for creating agent skill data records."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: Annotated[str, Field(description="ID of the agent this data belongs to")]
    skill: Annotated[str, Field(description="Name of the skill this data is for")]
    key: Annotated[str, Field(description="Key for this specific piece of data")]
    data: Annotated[Dict[str, Any], Field(description="JSON data stored for this key")]

    async def save(self) -> "AgentSkillData":
        """Save or update skill data.

        Returns:
            AgentSkillData: The saved agent skill data instance
        """
        async with get_session() as db:
            record = await db.scalar(
                select(AgentSkillDataTable).where(
                    AgentSkillDataTable.agent_id == self.agent_id,
                    AgentSkillDataTable.skill == self.skill,
                    AgentSkillDataTable.key == self.key,
                )
            )

            if record:
                # Update existing record
                record.data = self.data
            else:
                # Create new record
                record = AgentSkillDataTable(**self.model_dump())
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return AgentSkillData.model_validate(record)


class AgentSkillData(AgentSkillDataCreate):
    """Model for storing skill-specific data for agents.

    This model uses a composite primary key of (agent_id, skill, key) to store
    skill-specific data for agents in a flexible way.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this data was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this data was updated")
    ]

    @classmethod
    async def get(cls, agent_id: str, skill: str, key: str) -> Optional[dict]:
        """Get skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        async with get_session() as db:
            result = await db.scalar(
                select(AgentSkillDataTable).where(
                    AgentSkillDataTable.agent_id == agent_id,
                    AgentSkillDataTable.skill == skill,
                    AgentSkillDataTable.key == key,
                )
            )
            return result.data if result else None

    @classmethod
    async def clean_data(cls, agent_id: str):
        """Clean all skill data for an agent.

        Args:
            agent_id: ID of the agent
        """
        async with get_session() as db:
            await db.execute(
                delete(AgentSkillDataTable).where(
                    AgentSkillDataTable.agent_id == agent_id
                )
            )
            await db.commit()


class ThreadSkillDataTable(Base):
    """Database table model for storing skill-specific data for threads."""

    __tablename__ = "thread_skill_data"

    thread_id = Column(String, primary_key=True)
    skill = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False)
    data = Column(JSONB, nullable=True)
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


class ThreadSkillDataCreate(BaseModel):
    """Base model for creating thread skill data records."""

    model_config = ConfigDict(from_attributes=True)

    thread_id: Annotated[
        str, Field(description="ID of the thread this data belongs to")
    ]
    skill: Annotated[str, Field(description="Name of the skill this data is for")]
    key: Annotated[str, Field(description="Key for this specific piece of data")]
    agent_id: Annotated[str, Field(description="ID of the agent that owns this thread")]
    data: Annotated[Dict[str, Any], Field(description="JSON data stored for this key")]

    async def save(self) -> "ThreadSkillData":
        """Save or update skill data.

        Returns:
            ThreadSkillData: The saved thread skill data instance
        """
        async with get_session() as db:
            record = await db.scalar(
                select(ThreadSkillDataTable).where(
                    ThreadSkillDataTable.thread_id == self.thread_id,
                    ThreadSkillDataTable.skill == self.skill,
                    ThreadSkillDataTable.key == self.key,
                )
            )

            if record:
                # Update existing record
                record.data = self.data
                record.agent_id = self.agent_id
            else:
                # Create new record
                record = ThreadSkillDataTable(**self.model_dump())
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return ThreadSkillData.model_validate(record)


class ThreadSkillData(ThreadSkillDataCreate):
    """Model for storing skill-specific data for threads.

    This model uses a composite primary key of (thread_id, skill, key) to store
    skill-specific data for threads in a flexible way. It also includes agent_id
    as a required field for tracking ownership.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this data was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this data was updated")
    ]

    @classmethod
    async def get(cls, thread_id: str, skill: str, key: str) -> Optional[dict]:
        """Get skill data for a thread.

        Args:
            thread_id: ID of the thread
            skill: Name of the skill
            key: Data key

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        async with get_session() as db:
            record = await db.scalar(
                select(ThreadSkillDataTable).where(
                    ThreadSkillDataTable.thread_id == thread_id,
                    ThreadSkillDataTable.skill == skill,
                    ThreadSkillDataTable.key == key,
                )
            )
        return record.data if record else None

    @classmethod
    async def clean_data(
        cls,
        agent_id: str,
        thread_id: Annotated[
            str,
            Field(
                default="",
                description="Optional ID of the thread. If provided, only cleans data for that thread.",
            ),
        ],
    ):
        """Clean all skill data for a thread or agent.

        Args:
            agent_id: ID of the agent
            thread_id: Optional ID of the thread. If provided, only cleans data for that thread.
                      If empty, cleans all data for the agent.
        """
        async with get_session() as db:
            if thread_id and thread_id != "":
                await db.execute(
                    delete(ThreadSkillDataTable).where(
                        ThreadSkillDataTable.agent_id == agent_id,
                        ThreadSkillDataTable.thread_id == thread_id,
                    )
                )
            else:
                await db.execute(
                    delete(ThreadSkillDataTable).where(
                        ThreadSkillDataTable.agent_id == agent_id
                    )
                )
            await db.commit()


class SkillTable(Base):
    """Database table model for Skill."""

    __tablename__ = "skills"

    name = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    price_tier = Column(Integer, nullable=False, default=1)
    price_tier_self_key = Column(Integer, nullable=False, default=1)
    rate_limit_count = Column(Integer, nullable=True)
    rate_limit_minutes = Column(Integer, nullable=True)
    key_provider_agent_owner = Column(Boolean, nullable=False, default=False)
    key_provider_platform = Column(Boolean, nullable=False, default=False)
    key_provider_free = Column(Boolean, nullable=False, default=False)
    author = Column(String, nullable=True)
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


class Skill(BaseModel):
    """Pydantic model for Skill."""

    model_config = ConfigDict(from_attributes=True)

    name: Annotated[str, Field(description="Name of the skill")]
    category: Annotated[str, Field(description="Category of the skill")]
    price_tier: Annotated[
        int, Field(description="Price tier (1-5)", default=1, le=5, ge=1)
    ]
    price_tier_self_key: Annotated[
        int, Field(description="Self key for price tier", default=1, le=5, ge=1)
    ]
    rate_limit_count: Annotated[Optional[int], Field(description="Rate limit count")]
    rate_limit_minutes: Annotated[
        Optional[int], Field(description="Rate limit minutes")
    ]
    key_provider_agent_owner: Annotated[
        bool, Field(description="Agent owner can provide key", default=False)
    ]
    key_provider_platform: Annotated[
        bool, Field(description="Platform can provide key", default=False)
    ]
    key_provider_free: Annotated[
        bool, Field(description="Free key provider", default=False)
    ]
    author: Annotated[Optional[str], Field(description="Author of the skill")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this record was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this record was last updated")
    ]

    # helper to map price tier to Decimal price
    def _decimal_price_for_tier(self, tier: int) -> Decimal:
        mapping = {
            1: Decimal("1"),
            2: Decimal("2"),
            3: Decimal("5"),
            4: Decimal("10"),
            5: Decimal("20"),
        }
        try:
            return mapping[tier]
        except KeyError:
            raise ValueError(f"Invalid price tier: {tier}")

    @property
    def price(self) -> Decimal:
        return self._decimal_price_for_tier(self.price_tier)

    @property
    def price_self_key(self) -> Decimal:
        return self._decimal_price_for_tier(self.price_tier_self_key)
