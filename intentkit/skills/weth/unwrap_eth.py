"""WETH unwrap_eth skill - Unwrap WETH to ETH."""

from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.weth.base import WethBaseTool
from intentkit.skills.weth.constants import WETH_ABI, get_weth_address


class UnwrapEthInput(BaseModel):
    """Input schema for unwrap_eth."""

    amount_to_unwrap: str = Field(
        ...,
        description="Amount of WETH to unwrap (e.g. '0.1')",
    )


class WETHUnwrapEth(WethBaseTool):
    """Unwrap WETH to ETH.

    This tool unwraps WETH (Wrapped ETH) back to native ETH.
    """

    name: str = "weth_unwrap_eth"
    description: str = "Unwrap WETH to native ETH (1:1 conversion). Ensure sufficient WETH balance and ETH for gas."
    args_schema: ArgsSchema | None = UnwrapEthInput

    @override
    async def _arun(
        self,
        amount_to_unwrap: str,
    ) -> str:
        """Unwrap WETH to ETH.

        Args:
            amount_to_unwrap: Amount of WETH to unwrap in human-readable format.

        Returns:
            A message containing the unwrap result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()
            network_id = wallet.network_id

            # Get WETH address for this network
            weth_address = get_weth_address(network_id)
            if not weth_address:
                raise ToolException(
                    f"Error: WETH not supported on network {network_id}"
                )
            # Convert human-readable WETH amount to wei (WETH has 18 decimals)
            amount_decimal = Decimal(amount_to_unwrap)
            amount_in_wei = int(amount_decimal * Decimal(10**18))

            w3 = Web3()
            checksum_weth = w3.to_checksum_address(weth_address)
            checksum_address = w3.to_checksum_address(wallet.address)

            # Check WETH balance before unwrapping
            weth_balance = await wallet.call_contract(
                contract_address=checksum_weth,
                abi=ERC20_ABI,
                function_name="balanceOf",
                args=[checksum_address],
            )

            if weth_balance < amount_in_wei:
                weth_balance_formatted = Decimal(weth_balance) / Decimal(10**18)
                raise ToolException(
                    f"Error: Insufficient WETH balance. "
                    f"Requested to unwrap {amount_to_unwrap} WETH, "
                    f"but only {weth_balance_formatted} WETH is available."
                )

            # Encode withdraw function
            contract = w3.eth.contract(address=checksum_weth, abi=WETH_ABI)
            data = contract.encode_abi("withdraw", [amount_in_wei])

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_weth,
                data=data,
            )

            # Wait for receipt
            _ = await wallet.wait_for_receipt(tx_hash)

            return f"Unwrapped {amount_to_unwrap} WETH to ETH.\nTransaction hash: {tx_hash}"

        except Exception as e:
            raise ToolException(f"Error unwrapping WETH: {e!s}")
