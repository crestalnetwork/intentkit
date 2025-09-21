"""WOW AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class WowBaseTool(CDPBaseTool):
    """Base class for WOW tools."""

    @property
    def category(self) -> str:
        return "wow"
