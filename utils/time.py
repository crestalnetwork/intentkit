import time

from pydantic import BaseModel, Field, field_validator


class TimestampRange(BaseModel):
    """
    Represents a range of epoch timestamps. If the end timestamp is not provided, it defaults to the current time.
    If the user specifies the last n days, the start will be the current time minus n days in seconds, and the end will be the current time.
    If the user specifies the last n hours, the start will be the current time minus n hours in seconds, and the end will be the current time.
    If the user specifies the last n minutes, the start will be the current time minus n minutes in seconds, and the end will be the current time.

    Attributes:
        start: The starting timestamp (Unix epoch in seconds).
        end: The ending timestamp (Unix epoch in seconds).
    """

    start: int = Field(
        int(time.time()), description="Starting timestamp (Unix epoch in seconds)"
    )
    end: int = Field(
        int(time.time()), description="Ending timestamp (Unix epoch in seconds)"
    )

    @field_validator("end")
    def end_must_be_after_start(cls, value, info):
        """Validates that the end timestamp is after the start timestamp."""
        start = info.data.get("start")
        if start is not None and value <= start:
            raise ValueError("End timestamp must be greater than start timestamp.")
        return value
