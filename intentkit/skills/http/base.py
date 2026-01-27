from pydantic import BaseModel, Field

from intentkit.skills.base import IntentKitSkill


class HttpBaseTool(IntentKitSkill):
    """Base class for HTTP client tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    category: str = "TEMP_MARKER"
