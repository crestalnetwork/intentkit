"""System tool for getting the current time."""

from datetime import datetime
from typing import override

import pytz
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_tools.base import SystemTool


class CurrentTimeInput(BaseModel):
    """Input for CurrentTime tool."""

    timezone: str = Field(
        description="Timezone name, e.g. 'UTC', 'US/Pacific', 'Asia/Tokyo'.",
        default="UTC",
    )


class CurrentTimeTool(SystemTool):
    """Tool for getting the current time.

    This tool returns the current time converted to the specified timezone,
    along with the Unix timestamp (seconds since epoch, timezone-independent)
    for tools that need a numeric time value. By default, it returns the time
    in UTC.
    """

    name: str = "current_time"
    description: str = (
        "Get the current time in a specified timezone, including the Unix "
        "timestamp (seconds since epoch)."
    )
    args_schema: ArgsSchema | None = CurrentTimeInput

    @override
    async def _arun(self, timezone: str = "UTC") -> str:
        """Get the current time in the specified timezone.

        Args:
            timezone: The timezone to format the time in. Defaults to "UTC".

        Returns:
            A formatted string with the current time in the specified timezone
            and the Unix timestamp in seconds.
        """
        try:
            utc_now = datetime.now(pytz.UTC)

            if timezone.upper() != "UTC":
                tz = pytz.timezone(timezone)
                converted_time = utc_now.astimezone(tz)
            else:
                converted_time = utc_now

            formatted_time = converted_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            unix_timestamp = int(utc_now.timestamp())

            return f"Current time: {formatted_time}\nUnix timestamp: {unix_timestamp}"
        except pytz.exceptions.UnknownTimeZoneError:
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
            raise ToolException(
                f"Unknown timezone '{timezone}'.\n"
                f"Some common timezone options: {suggestion_str}"
            )
        except ToolException:
            raise
        except Exception as e:
            self.logger.exception("current_time failed: %s", e)
            raise ToolException(f"Failed to get current time: {e}") from e
