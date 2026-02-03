"""Base class for Casino tools."""

from intentkit.skills.base import IntentKitSkill


class CasinoBaseTool(IntentKitSkill):
    """Base class for Casino tools."""

    category: str = "casino"
