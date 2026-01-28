from langchain_core.tools import ArgsSchema
from pydantic import Field

from intentkit.skills.base import IntentKitSkill


class CommonBaseTool(IntentKitSkill):
    """Base class for common utility tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: ArgsSchema | None = None
    category: str = "common"
