from pydantic import BaseModel, Field

from intentkit.skills.base import IntentKitSkill


class CDPBaseTool(IntentKitSkill):
    """Base class for CDP tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    @property
    def category(self) -> str:
        return "cdp"
