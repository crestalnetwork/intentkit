from typing import Optional, Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.clients import get_cdp_client
from intentkit.skills.cdp.base import CDPBaseTool


class GetBalanceInput(BaseModel):
    """Input for GetBalance tool."""

    asset_id: Optional[str] = Field(
        default=None,
        description="The asset ID to get the balance for (e.g., 'eth', 'usdc', or a valid contract address). If not provided, returns all token balances.",
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

    name: str = "cdp_get_balance"
    description: str = (
        "This tool will get the balance of all the addresses in the wallet. If asset_id is provided, it returns the balance for that specific asset. "
        "If no asset_id is provided, it returns all token balances. "
        "Always use 'eth' for the native asset ETH and 'usdc' for USDC. "
        "Other valid asset IDs are: weth,dai,reth,brett,w,cbeth,axl,iotx,prime,aero,rsr,mog,tbtc,npc,yfi"
    )
    args_schema: Type[BaseModel] = GetBalanceInput

    async def _arun(self, asset_id: Optional[str] = None) -> str:
        """Async implementation of the tool to get balance.

        Args:
            asset_id (Optional[str]): The asset ID to get the balance for. If None, returns all token balances.

        Returns:
            str: A message containing the balance information or error message.
        """
        # Get network information from CDP client
        cdp_client = await get_cdp_client(self.agent_id, self.skill_store)
        provider = await cdp_client.get_wallet_provider()
        provider_config = await cdp_client.get_provider_config()
        network_id = provider_config.network_id

        # Map network_id to the format expected by the API
        network_mapping = {
            "base-mainnet": "base",
            "ethereum-mainnet": "ethereum",
        }
        api_network = network_mapping.get(network_id, network_id)

        # For native ETH balance, use the account's balance directly
        if asset_id and asset_id.lower() == "eth":
            try:
                # Get native balance using Web3
                balance_wei = provider.get_balance()
                balance_eth = balance_wei / (10**18)  # Convert from wei to ETH
                return f"ETH balance: {balance_eth} ETH"
            except Exception as e:
                return f"Error getting ETH balance: {e!s}"

        client = provider.get_client()
        async with client:
            account = await client.evm.get_account(provider.get_address())
            # If no asset_id provided, return all token balances
            if asset_id is None:
                # Get native ETH balance
                balance_wei = provider.get_balance()
                balance_eth = balance_wei / (10**18)  # Convert from wei to ETH

                # Get all token balances
                token_balances = await account.list_token_balances(api_network)

                result = [f"ETH balance: {balance_eth} ETH"]

                for balance in token_balances.balances:
                    result.append(
                        f"{balance.token.symbol} balance: {balance.amount.decimals} {balance.token.name}"
                    )

                return f"All balances for account {account.address}:\n" + "\n".join(
                    result
                )

            # For other tokens, try the list_token_balances API
            token_balances = await account.list_token_balances(api_network)

            # Find the balance for the specific asset
            target_balance = None
            for balance in token_balances.balances:
                if balance.token.symbol.lower() == asset_id.lower():
                    target_balance = balance
                    break

            if target_balance:
                return f"Balance for {asset_id} in account {account.address}: {target_balance.amount.decimals} {target_balance.token.name}"
            else:
                return f"No balance found for asset {asset_id} in account {account.address}"
