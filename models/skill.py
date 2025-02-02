from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, delete, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Session, SQLModel, select


class AgentSkillData(SQLModel, table=True):
    """Model for storing skill-specific data for agents.

    This model uses a composite primary key of (agent_id, skill, key) to store
    skill-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        skill: Name of the skill this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "agent_skill_data"

    agent_id: str = Field(primary_key=True)
    skill: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    data: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=True))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    @classmethod
    def get(
        cls, agent_id: str, skill: str, key: str, db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get skill data for an agent.

        Args:
            agent_id: ID of the agent
            skill: Name of the skill
            key: Data key
            db: Database session

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        result = db.exec(
            select(cls).where(
                cls.agent_id == agent_id,
                cls.skill == skill,
                cls.key == key,
            )
        ).first()
        return result.data if result else None

    def save(self, db: Session) -> None:
        """Save or update skill data.

        Args:
            db: Database session
        """
        existing = db.exec(
            select(self.__class__).where(
                self.__class__.agent_id == self.agent_id,
                self.__class__.skill == self.skill,
                self.__class__.key == self.key,
            )
        ).first()
        if existing:
            existing.data = self.data
            db.add(existing)
        else:
            db.add(self)

    @classmethod
    def clean_data(cls, agent_id: str, db: Session):
        db.exec(delete(cls).where(cls.agent_id == agent_id))


class ThreadSkillData(SQLModel, table=True):
    """Model for storing skill-specific data for threads.

    This model uses a composite primary key of (thread_id, skill, key) to store
    skill-specific data for threads in a flexible way. It also includes agent_id
    as a required field for tracking ownership.

    Attributes:
        thread_id: ID of the thread this data belongs to
        agent_id: ID of the agent that owns this thread
        skill: Name of the skill this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "thread_skill_data"

    thread_id: str = Field(primary_key=True)
    skill: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    agent_id: str = Field(nullable=False)
    data: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=True))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    @classmethod
    def get(
        cls, thread_id: str, skill: str, key: str, db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get skill data for a thread.

        Args:
            thread_id: ID of the thread
            skill: Name of the skill
            key: Data key
            db: Database session

        Returns:
            Dictionary containing the skill data if found, None otherwise
        """
        result = db.exec(
            select(cls).where(
                cls.thread_id == thread_id,
                cls.skill == skill,
                cls.key == key,
            )
        ).first()
        return result.data if result else None

    def save(self, db: Session) -> None:
        """Save or update skill data.

        Args:
            db: Database session
        """
        existing = db.exec(
            select(self.__class__).where(
                self.__class__.thread_id == self.thread_id,
                self.__class__.skill == self.skill,
                self.__class__.key == self.key,
            )
        ).first()
        if existing:
            existing.data = self.data
            existing.agent_id = self.agent_id
            db.add(existing)
        else:
            db.add(self)

    @classmethod
    def clean_data(cls, agent_id: str, thread_id: str, db: Session):
        if thread_id and thread_id != "":
            db.exec(
                delete(cls).where(
                    cls.agent_id == agent_id and cls.thread_id == thread_id
                )
            )
        else:
            db.exec(delete(cls).where(cls.agent_id == agent_id))
