"""Pyth AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class PythBaseTool(CDPBaseTool):
    """Base class for Pyth tools."""

    @property
    def category(self) -> str:
        return "pyth"
