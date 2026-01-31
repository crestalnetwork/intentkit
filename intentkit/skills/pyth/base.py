"""Pyth skills base class."""

from intentkit.skills.base import IntentKitSkill


class PythBaseTool(IntentKitSkill):
    """Base class for Pyth tools.

    Pyth skills fetch price data from the Pyth oracle network.
    These skills do not require a wallet as they only read data.
    """

    category: str = "pyth"
