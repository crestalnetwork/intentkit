from typing import Type

from pydantic import BaseModel, Field
from coinbase_agentkit import CdpEvmServerWalletProvider

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.cdp.base import CDPBaseTool


class GetBalanceInput(BaseModel):
    """Input for GetBalance tool."""

    asset_id: str = Field(
        description="The asset ID to get the balance for (e.g., 'eth', 'usdc', or a valid contract address)"
    )


class GetBalance(CDPBaseTool):
    """Tool for getting balance from CDP wallet.

    This tool uses the CDP API to get balance from the wallet address.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    agent_id: str
    skill_store: SkillStoreABC
    wallet_provider: CdpEvmServerWalletProvider | None = None

    name: str = "cdp_get_balance"
    description: str = (
        "This tool will get the balance of the wallet for a given asset. It takes the asset ID as input."
        "Always use 'eth' for the native asset ETH. For other assets, use their token symbol or contract address."
    )
    args_schema: Type[BaseModel] = GetBalanceInput

    async def _arun(self, asset_id: str) -> str:
        """Async implementation of the tool to get balance.

        Args:
            asset_id (str): The asset ID to get the balance for.

        Returns:
            str: A message containing the balance information or error message.
        """
        try:
            if not self.wallet_provider:
                from intentkit.clients.cdp import get_cdp_client
                cdp_client = await get_cdp_client(self.agent_id, self.skill_store)
                self.wallet_provider = await cdp_client.get_wallet_provider()

            # Get native ETH balance
            if asset_id.lower() == "eth":
                balance = self.wallet_provider.get_balance()
                address = self.wallet_provider.get_address()
                return f"ETH balance for address {address}: {balance} wei"
            else:
                # For other assets, we'd need additional implementation
                # This is a simplified version focusing on ETH
                return f"Balance checking for asset '{asset_id}' is not yet implemented in the updated API. Currently only 'eth' is supported."

        except Exception as e:
            return f"Error getting balance: {str(e)}"

    def _run(self, asset_id: str) -> str:
        """Sync implementation of the tool.

        This method is deprecated since we now have native async implementation in _arun.
        """
        raise NotImplementedError(
            "Use _arun instead, which is the async implementation"
        )
