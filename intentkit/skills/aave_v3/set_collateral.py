"""Aave V3 set collateral skill — enable/disable asset as collateral."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.constants import POOL_ABI, POOL_ADDRESSES
from intentkit.skills.aave_v3.utils import get_token_symbol

NAME = "aave_v3_set_collateral"


class SetCollateralInput(BaseModel):
    """Input for Aave V3 set collateral."""

    token_address: str = Field(description="ERC20 token contract address")
    use_as_collateral: bool = Field(
        description="True to enable as collateral, False to disable"
    )


class AaveV3SetCollateral(AaveV3BaseTool):
    """Enable or disable an asset as collateral on Aave V3."""

    name: str = NAME
    description: str = (
        "Enable or disable a supplied asset as collateral on Aave V3. "
        "Disabling collateral may affect your health factor and borrowing capacity. "
        "You can only disable collateral if it would not cause liquidation."
    )
    args_schema: ArgsSchema | None = SetCollateralInput

    @override
    async def _arun(
        self,
        token_address: str,
        use_as_collateral: bool,
        **kwargs: Any,
    ) -> str:
        try:
            chain_id = self._resolve_chain_id()
            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()

            pool_address = POOL_ADDRESSES[chain_id]
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_pool = Web3.to_checksum_address(pool_address)

            symbol = await get_token_symbol(w3, checksum_token, chain_id)

            pool = w3.eth.contract(address=checksum_pool, abi=POOL_ABI)
            calldata = pool.encode_abi(
                "setUserUseReserveAsCollateral",
                [checksum_token, use_as_collateral],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pool,
                data=calldata,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(
                    f"Set collateral transaction failed. Hash: {tx_hash}"
                )

            action = "Enabled" if use_as_collateral else "Disabled"

            return (
                f"**Aave V3 Set Collateral**\n"
                f"{action} {symbol} as collateral\n"
                f"Network: {self.get_agent_network_id()}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Set collateral failed: {e!s}")
