"""ERC20 AgentKit skills base class."""

from intentkit.skills.cdp.base import CDPBaseTool


class ERC20BaseTool(CDPBaseTool):
    """Base class for ERC20 tools."""

    @property
    def category(self) -> str:
        return "erc20"
