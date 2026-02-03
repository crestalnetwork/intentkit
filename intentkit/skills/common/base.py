from intentkit.skills.base import IntentKitSkill


class CommonBaseTool(IntentKitSkill):
    """Base class for common utility tools."""

    category: str = "common"
