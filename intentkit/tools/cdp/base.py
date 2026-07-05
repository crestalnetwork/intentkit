"""CDP wallet tools base class."""

from langchain_core.tools.base import ToolException

from intentkit.models.wallet import TeamWallet
from intentkit.tools.onchain import IntentKitOnChainTool


class CDPBaseTool(IntentKitOnChainTool):
    """Base class for CDP wallet tools.

    CDP tools provide basic wallet operations like getting balances,
    wallet details, and transferring native tokens.

    These tools explicitly require a CDP wallet provider.
    """

    category: str = "cdp"

    async def ensure_cdp_provider(self, wallet_address: str) -> TeamWallet:
        """Resolve a team wallet and ensure its provider is CDP.

        This is a read-side check (no signing authorization involved).
        """
        wallet = await self.resolve_wallet(wallet_address)
        if wallet.wallet_provider != "cdp":
            raise ToolException(
                "This tool is only available when the wallet provider is 'cdp'."
            )
        return wallet
