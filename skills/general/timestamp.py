import time
from typing import Type

import dateparser
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import GeneralBaseTool


class CurrentEpochTimestampInput(BaseModel):
    pass


class CurrentEpochTimestampOutput(BaseModel):
    timestamp: int = Field(..., description="The current epoch timestamp")


class CurrentEpochTimestampTool(GeneralBaseTool):
    name: str = "general_current_epoch_timestamp"
    description: str = (
        """
        Useful for getting the current Unix epoch timestamp in seconds. you should use this tool before any tool that 
        needs the current epoch timestamp. This returns UTC epoch timestamp.
        """
    )

    args_schema: Type[BaseModel] = CurrentEpochTimestampInput

    def _run(self) -> CurrentEpochTimestampOutput:
        """Returns the current epoch timestamp."""
        return CurrentEpochTimestampOutput(timestamp=int(time.time()))

    async def _arun(self) -> CurrentEpochTimestampOutput:
        """Returns the current epoch timestamp asynchronously."""
        return CurrentEpochTimestampOutput(timestamp=int(time.time()))


class GetRelativeTimeParserInput(BaseModel):
    relative_time_str: str = Field(
        ..., description="Human-readable relative time string"
    )


class GetRelativeTimeParser(GeneralBaseTool):
    """
    This is a tool for parsing human-readable relative time strings and converting them into epoch timestamps in seconds. if the output of this tool
    is going to be used in another tool, you should execute this tool every time.

    Attributes:
        name (str): The name of the tool.
        description (str): A detailed description of the tool's functionality and supported relative time expressions.
        args_schema (Type[BaseModel]): The schema for the input arguments.

    Methods:
        _run(relative_time_str: str) -> int:
            Synchronous method to parse a relative time string. Always raises NotImplementedError to indicate that this method should not be used.

        _arun(relative_time_str: str) -> int:
            Asynchronous method to parse a human-readable relative time string and return the corresponding epoch timestamp in seconds.
                int: Epoch timestamp of the parsed relative time string.
    """

    name: str = "general_relative_time_parser"
    description: str = (
        """
        Parses a human-readable relative time string and returns the corresponding epoch timestamp in seconds. if the output of this tool
        is going to be used in another tool, you should execute this tool every time
        This tool supports a wide range of relative time expressions, including:
        - Past durations: "last 5 days", "last 2 hours", "last 10 minutes", "yesterday", "a week ago", "3 months ago", "2 years ago"
        - Future durations: "in 6 days", "in 4 hours", "in 20 minutes", "tomorrow", "next week", "in 3 months", "in 2 years"
        - Specific relative points: "today", "now", "this week", "next Monday", "last Friday"
        - Fuzzy relative times: "a couple of days ago", "few hours from now"
        - Combined relative dates and times: "last week at 3pm", "tomorrow morning"
        """
    )

    args_schema: Type[BaseModel] = GetRelativeTimeParserInput

    def _run(self, relative_time_str: str) -> int:
        """
        Synchronous method to parse a relative time string.

        Args:
            relative_time_str (str): The relative time string to be parsed.

        Raises:
            NotImplementedError: Always raised to indicate that this method should not be used.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, relative_time_str: str) -> int:
        """
        Parses a human-readable relative time string and returns the corresponding epoch timestamp in seconds.

        Args:
            relative_time_str (str): The human-readable relative time string to be parsed.

        Returns:
            int: epoch timestamp of the parsed relative time string.

        Raises:
            ToolException: If the date string could not be parsed.
        """
        parsed_date = dateparser.parse(relative_time_str)

        if parsed_date is None:
            raise ToolException(f"Could not parse date string: {relative_time_str}")

        timestamp = int(parsed_date.timestamp())

        return timestamp
