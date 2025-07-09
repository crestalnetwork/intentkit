import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, Optional

from intentkit.models.base import Base
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB


class AgentSkillDataTable(Base):
    """Database table model for storing skill-specific data for agents."""

    __tablename__ = "agent_skill_data"

    agent_id = Column(String, primary_key=True)
    skill = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    data = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    size = Column(Integer, nullable=False, default=0)
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

        Raises:
            Exception: If the total size would exceed the 10MB limit
        """
        # Calculate the size of the data
        data_size = len(json.dumps(self.data).encode("utf-8"))

        async with get_session() as db:
            # Check current total size for this agent
            current_total = await AgentSkillData.total_size(self.agent_id)

            record = await db.scalar(
                select(AgentSkillDataTable).where(
                    AgentSkillDataTable.agent_id == self.agent_id,
                    AgentSkillDataTable.skill == self.skill,
                    AgentSkillDataTable.key == self.key,
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
                raise Exception(
                    f"Total size would exceed 10MB limit. Current: {current_total}, New: {new_total}"
                )

            if record:
                # Update existing record
                record.data = self.data
                record.size = data_size
            else:
                # Create new record
                record = AgentSkillDataTable(
                    agent_id=self.agent_id,
                    skill=self.skill,
                    key=self.key,
                    data=self.data,
                    size=data_size,
                )

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

    size: Annotated[int, Field(description="Size of the data in bytes")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this data was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this data was updated")
    ]

    @classmethod
    async def total_size(cls, agent_id: str) -> int:
        """Calculate the total size of all skill data for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            int: Total size in bytes of all skill data for the agent
        """
        async with get_session() as db:
            result = await db.scalar(
                select(func.coalesce(func.sum(AgentSkillDataTable.size), 0)).where(
                    AgentSkillDataTable.agent_id == agent_id
                )
            )
            return result or 0

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
    async def delete(cls, agent_id: str, skill: str, key: str) -> None:
        """Delete skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key
        """
        async with get_session() as db:
            await db.execute(
                delete(AgentSkillDataTable).where(
                    AgentSkillDataTable.agent_id == agent_id,
                    AgentSkillDataTable.skill == skill,
                    AgentSkillDataTable.key == key,
                )
            )
            await db.commit()

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
    data = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
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
    enabled = Column(Boolean, nullable=False, default=True)
    category = Column(String, nullable=False)
    config_name = Column(String, nullable=True)
    price_level = Column(Integer, nullable=True)
    price = Column(Numeric(22, 4), nullable=False, default=1)
    price_self_key = Column(Numeric(22, 4), nullable=False, default=1)
    rate_limit_count = Column(Integer, nullable=True)
    rate_limit_minutes = Column(Integer, nullable=True)
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

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    name: Annotated[str, Field(description="Name of the skill")]
    enabled: Annotated[bool, Field(description="Is this skill enabled?")]
    category: Annotated[str, Field(description="Category of the skill")]
    config_name: Annotated[Optional[str], Field(description="Config name of the skill")]
    price_level: Annotated[
        Optional[int], Field(description="Price level for this skill")
    ]
    price: Annotated[
        Decimal, Field(description="Price for this skill", default=Decimal("1"))
    ]
    price_self_key: Annotated[
        Decimal,
        Field(description="Price for this skill with self key", default=Decimal("1")),
    ]
    rate_limit_count: Annotated[Optional[int], Field(description="Rate limit count")]
    rate_limit_minutes: Annotated[
        Optional[int], Field(description="Rate limit minutes")
    ]
    author: Annotated[Optional[str], Field(description="Author of the skill")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this record was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this record was last updated")
    ]

    @staticmethod
    async def get(name: str) -> Optional["Skill"]:
        """Get a skill by name with Redis caching.

        The skill is cached in Redis for 3 minutes.

        Args:
            name: Name of the skill to retrieve

        Returns:
            Skill: The skill if found, None otherwise
        """
        # Redis cache key for skill
        cache_key = f"intentkit:skill:{name}"
        cache_ttl = 180  # 3 minutes in seconds

        # Try to get from Redis cache first
        redis = get_redis()
        cached_data = await redis.get(cache_key)

        if cached_data:
            # If found in cache, deserialize and return
            try:
                return Skill.model_validate_json(cached_data)
            except (json.JSONDecodeError, TypeError):
                # If cache is corrupted, invalidate it
                await redis.delete(cache_key)

        # If not in cache or cache is invalid, get from database
        async with get_session() as session:
            # Query the database for the skill
            stmt = select(SkillTable).where(SkillTable.name == name)
            skill = await session.scalar(stmt)

            # If skill doesn't exist, return None
            if not skill:
                return None

            # Convert to Skill model
            skill_model = Skill.model_validate(skill)

            # Cache the skill in Redis
            await redis.set(cache_key, skill_model.model_dump_json(), ex=cache_ttl)

            return skill_model

    @staticmethod
    async def get_by_config_name(category: str, config_name: str) -> Optional["Skill"]:
        """Get a skill by category and config_name.

        Args:
            category: Category of the skill
            config_name: Config name of the skill

        Returns:
            Skill: The skill if found, None otherwise
        """
        async with get_session() as session:
            # Query the database for the skill
            stmt = select(SkillTable).where(
                SkillTable.category == category, SkillTable.config_name == config_name
            )
            skill = await session.scalar(stmt)

            # If skill doesn't exist, return None
            if not skill:
                return None

            # Convert to Skill model
            return Skill.model_validate(skill)
