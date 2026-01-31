"""Basename skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class BasenameBaseTool(IntentKitOnChainSkill):
    """Base class for Basename tools."""

    category: str = "basename"
