import logging
from datetime import datetime
from typing import Type

import pytz
from pydantic import BaseModel, Field

from intentkit.skills.common.base import CommonBaseTool

logger = logging.getLogger(__name__)


class CurrentTimeInput(BaseModel):
    """Input for CurrentTime tool."""

    timezone: str = Field(
        description="Timezone to format the time in (e.g., 'UTC', 'US/Pacific', 'Europe/London', 'Asia/Tokyo'). Default is UTC.",
        default="UTC",
    )


class CurrentTime(CommonBaseTool):
    """Tool for getting the current time.

    This tool returns the current time and converts it to the specified timezone.
    By default, it returns the time in UTC.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "common_current_time"
    description: str = (
        "Get the current time, converted to a specified timezone.\n"
        "You must call this tool whenever the user asks for the time."
    )
    args_schema: Type[BaseModel] = CurrentTimeInput

    async def _arun(self, timezone: str, **kwargs) -> str:
        """Implementation of the tool to get the current time.

        Args:
            timezone (str): The timezone to format the time in. Defaults to "UTC".

        Returns:
            str: A formatted string with the current time in the specified timezone.
        """
        # Get current UTC time
        utc_now = datetime.now(pytz.UTC)

        # Convert to the requested timezone
        if timezone.upper() != "UTC":
            try:
                tz = pytz.timezone(timezone)
                converted_time = utc_now.astimezone(tz)
            except pytz.exceptions.UnknownTimeZoneError:
                # Provide some suggestions for common timezones
                common_timezones = [
                    "US/Eastern",
                    "US/Central",
                    "US/Pacific",
                    "Europe/London",
                    "Europe/Paris",
                    "Europe/Berlin",
                    "Asia/Shanghai",
                    "Asia/Tokyo",
                    "Asia/Singapore",
                    "Australia/Sydney",
                ]
                suggestion_str = ", ".join([f"'{tz}'" for tz in common_timezones])
                return (
                    f"Error: Unknown timezone '{timezone}'. Using UTC instead.\n"
                    f"Some common timezone options: {suggestion_str}"
                )
        else:
            converted_time = utc_now

        # Format the time
        formatted_time = converted_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        return f"Current time: {formatted_time}"
