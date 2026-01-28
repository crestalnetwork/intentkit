"""ERC20 AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class ERC20BaseTool(CDPBaseTool):
    """Base class for ERC20 tools."""

    category: str = "erc20"
