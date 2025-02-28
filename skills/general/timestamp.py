import time
from typing import Type

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
