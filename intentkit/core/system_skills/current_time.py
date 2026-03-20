"""System skill for getting the current time."""

from datetime import datetime
from typing import override

import pytz
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill


class CurrentTimeInput(BaseModel):
    """Input for CurrentTime tool."""

    timezone: str = Field(
        description="Timezone name, e.g. 'UTC', 'US/Pacific', 'Asia/Tokyo'.",
        default="UTC",
    )


class CurrentTimeSkill(SystemSkill):
    """Tool for getting the current time.

    This tool returns the current time and converts it to the specified timezone.
    By default, it returns the time in UTC.
    """

    name: str = "current_time"
    description: str = "Get the current time in a specified timezone."
    args_schema: ArgsSchema | None = CurrentTimeInput

    @override
    async def _arun(self, timezone: str = "UTC") -> str:
        """Get the current time in the specified timezone.

        Args:
            timezone: The timezone to format the time in. Defaults to "UTC".

        Returns:
            A formatted string with the current time in the specified timezone.
        """
        try:
            utc_now = datetime.now(pytz.UTC)

            if timezone.upper() != "UTC":
                tz = pytz.timezone(timezone)
                converted_time = utc_now.astimezone(tz)
            else:
                converted_time = utc_now

            formatted_time = converted_time.strftime("%Y-%m-%d %H:%M:%S %Z")

            return f"Current time: {formatted_time}"
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
            self.logger.error("current_time failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to get current time: {e}") from e
