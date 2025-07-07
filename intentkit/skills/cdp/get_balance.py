from typing import Type

from cdp import EvmServerAccount
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import get_cdp_client
from intentkit.skills.cdp.base import CDPBaseTool


class GetBalanceInput(BaseModel):
    """Input for GetBalance tool."""

    asset_id: str = Field(
        description="The asset ID to get the balance for (e.g., 'eth', 'usdc', or a valid contract address)"
    )


class GetBalance(CDPBaseTool):
    """Tool for getting balance from CDP wallet.

    This tool uses the CDP API to get balance for all addresses in a wallet for a given asset.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    agent_id: str
    skill_store: SkillStoreABC
    account: EvmServerAccount | None = None

    name: str = "cdp_get_balance"
    description: str = (
        "This tool will get the balance of all the addresses in the wallet for a given asset. It takes the asset ID as input."
        "Always use 'eth' for the native asset ETH and 'usdc' for USDC. "
        "Other valid asset IDs are: weth,dai,reth,brett,w,cbeth,axl,iotx,prime,aero,rsr,mog,tbtc,npc,yfi"
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
            if not self.account:
                return "Failed to get account."

            # Get network information from CDP client
            cdp_client = await get_cdp_client(self.agent_id, self.skill_store)
            provider_config = await cdp_client.get_provider_config()
            network_id = provider_config.network_id

            # Map network_id to the format expected by the API
            network_mapping = {
                "base-mainnet": "base",
                "base-sepolia": "base-sepolia",
                "ethereum": "ethereum",
                "ethereum-mainnet": "ethereum",
            }
            api_network = network_mapping.get(network_id, network_id)

            # For native ETH balance, use the account's balance directly
            if asset_id.lower() == "eth":
                try:
                    # Get native balance using Web3
                    balance_wei = await self.account.get_balance()
                    balance_eth = balance_wei / (10**18)  # Convert from wei to ETH
                    return f"ETH balance for account {self.account.address}: {balance_eth} ETH"
                except Exception as e:
                    return f"Error getting ETH balance: {e!s}"

            # For other tokens, try the list_token_balances API
            try:
                # list_token_balances returns all token balances for the account
                token_balances = await self.account.list_token_balances(api_network)

                # Find the balance for the specific asset
                target_balance = None
                for balance in token_balances:
                    if balance.asset_id.lower() == asset_id.lower():
                        target_balance = balance
                        break

                if target_balance:
                    return f"Balance for {asset_id} in account {self.account.address}: {target_balance.amount} {target_balance.asset_id}"
                else:
                    return f"No balance found for asset {asset_id} in account {self.account.address}"

            except Exception as e:
                return f"Error getting balance for account: {e!s}"

        except Exception as e:
            return f"Error getting balance: {str(e)}"

    def _run(self, asset_id: str) -> str:
        """Sync implementation of the tool.

        This method is deprecated since we now have native async implementation in _arun.
        """
        raise NotImplementedError(
            "Use _arun instead, which is the async implementation"
        )
