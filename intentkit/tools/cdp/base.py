"""CDP wallet tools base class."""

from langchain_core.tools.base import ToolException

from intentkit.tools.onchain import IntentKitOnChainTool


class CDPBaseTool(IntentKitOnChainTool):
    """Base class for CDP wallet tools.

    CDP tools provide basic wallet operations like getting balances,
    wallet details, and transferring native tokens.

    These tools explicitly require a CDP wallet provider.
    """

    category: str = "cdp"

    async def ensure_cdp_provider(self) -> None:
        """Ensure the agent's wallet provider is CDP."""
        if await self.get_agent_wallet_provider_type() != "cdp":
            raise ToolException(
                "This tool is only available when the wallet provider is 'cdp'."
            )
