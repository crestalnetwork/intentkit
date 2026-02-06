from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from pydantic import Field as PydanticField


class AgentAutonomousStatus(str, Enum):
    """Autonomous task execution status."""

    WAITING = "waiting"
    RUNNING = "running"
    ERROR = "error"


class AutonomousCreateRequest(BaseModel):
    """Request model for creating a new autonomous task."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: str | None = PydanticField(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = PydanticField(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str = PydanticField(
        ...,
        description="Cron expression for scheduling operations",
    )
    prompt: str = PydanticField(
        ...,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool = PydanticField(
        default=False,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool = PydanticField(
        default=True,
        description="Whether to retain conversation memory between autonomous runs.",
    )


class AutonomousUpdateRequest(BaseModel):
    """Request model for modifying an autonomous task."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: str | None = PydanticField(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = PydanticField(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str | None = PydanticField(
        default=None,
        description="Cron expression for scheduling operations",
    )
    prompt: str | None = PydanticField(
        default=None,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool | None = PydanticField(
        default=None,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool | None = PydanticField(
        default=None,
        description="Whether to retain conversation memory between autonomous runs.",
    )


def minutes_to_cron(minutes: int) -> str:
    """Convert minutes interval to a cron expression.

    This is a simple conversion that creates a cron expression like `*/n * * * *`
    where n is the number of minutes.

    Args:
        minutes: Interval in minutes (should be >= 1)

    Returns:
        A cron expression string
    """
    if minutes <= 0:
        minutes = 5  # Default to 5 minutes if invalid
    if minutes >= 60:
        # For intervals >= 60 minutes, use hourly scheduling
        hours = minutes // 60
        if hours >= 24:
            # Run once a day at midnight
            return "0 0 * * *"
        return f"0 */{hours} * * *"
    return f"*/{minutes} * * * *"


class AgentAutonomous(BaseModel):
    """Autonomous agent configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the autonomous configuration",
            default_factory=lambda: str(XID()),
            min_length=1,
            max_length=20,
            pattern=r"^[a-z0-9-]+$",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    name: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Display name of the autonomous configuration",
            max_length=50,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None
    description: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Description of the autonomous configuration",
            max_length=200,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None
    minutes: Annotated[
        int | None,
        PydanticField(
            default=None,
            description="Interval in minutes between operations. Mutually exclusive with cron.",
            json_schema_extra={
                "x-group": "autonomous",
                "deprecated": True,
            },
        ),
    ] = None
    cron: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Cron expression for scheduling operations, mutually exclusive with minutes",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Special prompt used during autonomous operation",
            max_length=20000,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    enabled: Annotated[
        bool | None,
        PydanticField(
            default=False,
            description="Whether the autonomous configuration is enabled",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None
    has_memory: Annotated[
        bool | None,
        PydanticField(
            default=True,
            description="Whether to retain conversation memory between autonomous runs. If False, thread memory is cleared before each run.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None
    status: Annotated[
        AgentAutonomousStatus | None,
        PydanticField(
            default=None,
            description="Current execution status for the autonomous task.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None
    next_run_time: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Next scheduled run time for the autonomous task.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ] = None

    @field_serializer("next_run_time")
    @classmethod
    def serialize_next_run_time(cls, v: datetime | None) -> str | None:
        """Serialize datetime to ISO format string for JSON compatibility."""
        if v is None:
            return None
        return v.isoformat()

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v:
            raise ValueError("id cannot be empty")
        if len(v.encode()) > 20:
            raise ValueError("id must be at most 20 bytes")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "id must contain only lowercase letters, numbers, and dashes"
            )
        return v

    def normalize_status_defaults(self) -> "AgentAutonomous":
        """Normalize the autonomous task configuration.

        This method:
        1. Converts deprecated `minutes` field to `cron` expression
        2. Clears status/next_run_time when task is disabled
        3. Sets default status to WAITING when task is enabled
        """
        updates: dict[str, object] = {}

        # Convert minutes to cron if minutes is set but cron is not
        if self.minutes is not None and not self.cron:
            updates["cron"] = minutes_to_cron(self.minutes)
            updates["minutes"] = None  # Clear minutes after conversion

        if not self.enabled:
            if self.status is not None or self.next_run_time is not None:
                updates["status"] = None
                updates["next_run_time"] = None
        elif self.status is None:
            updates["status"] = AgentAutonomousStatus.WAITING

        if updates:
            return self.model_copy(update=updates)
        return self
