from typing import Type

from cdp import Wallet
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
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
    wallet: Wallet | None = None

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
            if not self.wallet:
                return "Failed to get wallet."

            # for each address in the wallet, get the balance for the asset
            balances = {}

            try:
                for address in self.wallet.addresses:
                    balance = address.balance(asset_id)
                    balances[address.address_id] = balance
            except Exception as e:
                return f"Error getting balance for all addresses in the wallet: {e!s}"

            # Format each balance entry on a new line
            balance_lines = [
                f"  {addr}: {balance}" for addr, balance in balances.items()
            ]
            formatted_balances = "\n".join(balance_lines)
            return f"Balances for wallet {self.wallet.id}:\n{formatted_balances}"

        except Exception as e:
            return f"Error getting balance: {str(e)}"

    def _run(self, asset_id: str) -> str:
        """Sync implementation of the tool.

        This method is deprecated since we now have native async implementation in _arun.
        """
        raise NotImplementedError(
            "Use _arun instead, which is the async implementation"
        )
