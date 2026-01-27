from pydantic import Field

from intentkit.skills.base import IntentKitSkill


class AIXBTBaseTool(IntentKitSkill):
    """Base class for AIXBT API tools."""

    description: str = Field(description="A description of what the tool does")
