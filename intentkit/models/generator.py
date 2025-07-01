"""Agent Generation Log Model.

This module defines the database models for logging agent generation operations,
including token usage, prompts, AI responses, and generation metadata.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from epyxid import XID
from intentkit.models.base import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.ext.asyncio import AsyncSession


class AgentGenerationLogTable(Base):
    """Agent generation log database table model."""

    __tablename__ = "agent_generation_logs"

    id = Column(
        String,
        primary_key=True,
    )
    user_id = Column(
        String,
        nullable=True,
    )
    prompt = Column(
        Text,
        nullable=False,
    )
    existing_agent_id = Column(
        String,
        nullable=True,
    )
    is_update = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    generated_agent_schema = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    identified_skills = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    # LLM API response data
    llm_model = Column(
        String,
        nullable=True,
    )
    total_tokens = Column(
        Integer,
        default=0,
    )
    input_tokens = Column(
        Integer,
        default=0,
    )
    cached_input_tokens = Column(
        Integer,
        default=0,
    )
    output_tokens = Column(
        Integer,
        default=0,
    )
    input_tokens_details = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    completion_tokens_details = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    # Performance metrics
    generation_time_ms = Column(
        Integer,
        nullable=True,
    )
    retry_count = Column(
        Integer,
        default=0,
    )
    validation_errors = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    # Status and results
    success = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    error_message = Column(
        Text,
        nullable=True,
    )
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )


class AgentGenerationLogCreate(BaseModel):
    """Model for creating agent generation log entries."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the generation log",
        ),
    ]
    user_id: Optional[str] = Field(
        None,
        description="User ID who initiated the generation",
    )
    prompt: str = Field(
        ...,
        description="The original prompt used for generation",
    )
    existing_agent_id: Optional[str] = Field(
        None,
        description="ID of existing agent if this is an update operation",
    )
    is_update: bool = Field(
        False,
        description="Whether this is an update to existing agent",
    )


class AgentGenerationLog(BaseModel):
    """Agent generation log model."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
    )

    id: str
    user_id: Optional[str] = None
    prompt: str
    existing_agent_id: Optional[str] = None
    is_update: bool = False
    generated_agent_schema: Optional[dict] = None
    identified_skills: Optional[dict] = None
    llm_model: Optional[str] = None
    total_tokens: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    input_tokens_details: Optional[dict] = None
    completion_tokens_details: Optional[dict] = None
    generation_time_ms: Optional[int] = None
    retry_count: int = 0
    validation_errors: Optional[dict] = None
    success: bool = False
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        log_data: AgentGenerationLogCreate,
    ) -> "AgentGenerationLog":
        """Create a new agent generation log entry.

        Args:
            session: Database session
            log_data: Log data to create

        Returns:
            Created log instance
        """
        # Create database record
        log_record = AgentGenerationLogTable(
            id=log_data.id,
            user_id=log_data.user_id,
            prompt=log_data.prompt,
            existing_agent_id=log_data.existing_agent_id,
            is_update=log_data.is_update,
        )

        session.add(log_record)
        await session.commit()
        await session.refresh(log_record)

        return cls.model_validate(log_record)

    async def update_completion(
        self,
        session: AsyncSession,
        generated_agent_schema: Optional[dict] = None,
        identified_skills: Optional[dict] = None,
        llm_model: Optional[str] = None,
        total_tokens: int = 0,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        input_tokens_details: Optional[dict] = None,
        completion_tokens_details: Optional[dict] = None,
        generation_time_ms: Optional[int] = None,
        retry_count: int = 0,
        validation_errors: Optional[dict] = None,
        success: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the log entry with completion data.

        Args:
            session: Database session
            generated_agent_schema: The generated agent schema
            identified_skills: Skills identified during generation
            llm_model: LLM model used
            total_tokens: Total tokens used
            input_tokens: Input tokens used
            cached_input_tokens: Cached input tokens used (for cost calculation)
            output_tokens: Output tokens used
            input_tokens_details: Detailed input token breakdown
            completion_tokens_details: Detailed completion token breakdown
            generation_time_ms: Generation time in milliseconds
            retry_count: Number of retries attempted
            validation_errors: Any validation errors encountered
            success: Whether generation was successful
            error_message: Error message if generation failed
        """
        # Get the database record
        log_record = await session.get(AgentGenerationLogTable, self.id)
        if not log_record:
            return

        # Update fields
        log_record.generated_agent_schema = generated_agent_schema
        log_record.identified_skills = identified_skills
        log_record.llm_model = llm_model
        log_record.total_tokens = total_tokens
        log_record.input_tokens = input_tokens
        log_record.cached_input_tokens = cached_input_tokens
        log_record.output_tokens = output_tokens
        log_record.input_tokens_details = input_tokens_details
        log_record.completion_tokens_details = completion_tokens_details
        log_record.generation_time_ms = generation_time_ms
        log_record.retry_count = retry_count
        log_record.validation_errors = validation_errors
        log_record.success = success
        log_record.error_message = error_message
        log_record.completed_at = datetime.now(timezone.utc)

        session.add(log_record)
        await session.commit()
        await session.refresh(log_record)

        # Update this instance
        self.generated_agent_schema = log_record.generated_agent_schema
        self.identified_skills = log_record.identified_skills
        self.llm_model = log_record.llm_model
        self.total_tokens = log_record.total_tokens
        self.input_tokens = log_record.input_tokens
        self.cached_input_tokens = log_record.cached_input_tokens
        self.output_tokens = log_record.output_tokens
        self.input_tokens_details = log_record.input_tokens_details
        self.completion_tokens_details = log_record.completion_tokens_details
        self.generation_time_ms = log_record.generation_time_ms
        self.retry_count = log_record.retry_count
        self.validation_errors = log_record.validation_errors
        self.success = log_record.success
        self.error_message = log_record.error_message
        self.completed_at = log_record.completed_at

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        log_id: str,
    ) -> Optional["AgentGenerationLog"]:
        """Get an agent generation log by ID.

        Args:
            session: Database session
            log_id: Log ID

        Returns:
            Log instance if found, None otherwise
        """
        result = await session.execute(
            select(AgentGenerationLogTable).where(AgentGenerationLogTable.id == log_id)
        )
        log_record = result.scalar_one_or_none()

        if log_record:
            return cls.model_validate(log_record)
        return None

    @classmethod
    async def get_by_user(
        cls,
        session: AsyncSession,
        user_id: str,
        limit: int = 50,
    ) -> list["AgentGenerationLog"]:
        """Get agent generation logs for a user.

        Args:
            session: Database session
            user_id: User ID
            limit: Maximum number of logs to return

        Returns:
            List of log instances
        """
        result = await session.execute(
            select(AgentGenerationLogTable)
            .where(AgentGenerationLogTable.user_id == user_id)
            .order_by(AgentGenerationLogTable.created_at.desc())
            .limit(limit)
        )
        log_records = result.scalars().all()

        return [cls.model_validate(record) for record in log_records]
