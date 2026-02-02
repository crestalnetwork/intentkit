from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, field_serializer, field_validator
from pydantic import Field as PydanticField


class AgentAutonomousStatus(str, Enum):
    """Autonomous task execution status."""

    WAITING = "waiting"
    RUNNING = "running"
    ERROR = "error"


class AgentAutonomous(BaseModel):
    """Autonomous agent configuration."""

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
    ]
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
    ]
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
    ]
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
    ]
    has_memory: Annotated[
        bool | None,
        PydanticField(
            default=True,
            description="Whether to retain conversation memory between autonomous runs. If False, thread memory is cleared before each run.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    status: Annotated[
        AgentAutonomousStatus | None,
        PydanticField(
            default=None,
            description="Current execution status for the autonomous task.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    next_run_time: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Next scheduled run time for the autonomous task.",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]

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
        if not self.enabled:
            if self.status is not None or self.next_run_time is not None:
                return self.model_copy(update={"status": None, "next_run_time": None})
            return self
        if self.status is None:
            return self.model_copy(update={"status": AgentAutonomousStatus.WAITING})
        return self
