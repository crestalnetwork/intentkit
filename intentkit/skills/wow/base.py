"""WOW AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class WowBaseTool(CDPBaseTool):
    """Base class for WOW tools."""

    category: str = "wow"
