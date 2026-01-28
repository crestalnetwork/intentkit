"""WETH AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class WethBaseTool(CDPBaseTool):
    """Base class for WETH tools."""

    category: str = "weth"
