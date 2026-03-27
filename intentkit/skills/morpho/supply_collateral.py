"""Morpho supply collateral skill — supply collateral to a Morpho Blue market."""

import asyncio
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import (
    MORPHO_BLUE_ABI,
    MORPHO_BLUE_ADDRESS,
)


class SupplyCollateralInput(BaseModel):
    """Input for Morpho Blue supply collateral."""

    market_id: str = Field(description="Morpho Blue market ID (bytes32 hex string)")
    amount: str = Field(
        description="Amount of collateral in whole units (e.g. '1' for 1 WETH)"
    )


class MorphoSupplyCollateral(MorphoBaseTool):
    """Supply collateral to a Morpho Blue market."""

    name: str = "morpho_supply_collateral"
    description: str = (
        "Supply collateral to a Morpho Blue market. "
        "Provide market_id (bytes32) and amount in whole units. "
        "The collateral token is determined by the market."
    )
    args_schema: ArgsSchema | None = SupplyCollateralInput

    @override
    async def _arun(
        self,
        market_id: str,
        amount: str,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet()
            self._validate_network(wallet.network_id)
            w3 = self.web3_client()

            (
                loan_token,
                collateral_token,
                oracle,
                irm,
                lltv,
            ) = await self._get_market_params(w3, market_id)

            checksum_morpho = Web3.to_checksum_address(MORPHO_BLUE_ADDRESS)
            wallet_address = Web3.to_checksum_address(wallet.address)

            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(collateral_token), abi=ERC20_ABI
            )
            decimals, symbol = await asyncio.gather(
                token_contract.functions.decimals().call(),
                token_contract.functions.symbol().call(),
            )

            amount_decimal = Decimal(amount)
            if amount_decimal <= Decimal("0"):
                raise ToolException("Error: Amount must be greater than 0")
            atomic_amount = int(amount_decimal * (10**decimals))

            approve_data = token_contract.encode_abi(
                "approve", [checksum_morpho, atomic_amount]
            )
            approve_tx = await wallet.send_transaction(
                to=collateral_token, data=approve_data
            )
            receipt = await wallet.wait_for_receipt(approve_tx)
            if receipt.get("status", 0) != 1:
                raise ToolException(
                    f"Error: Approval transaction failed. Hash: {approve_tx}"
                )

            market_params = (loan_token, collateral_token, oracle, irm, lltv)

            morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)
            call_data = morpho.encode_abi(
                "supplyCollateral",
                [market_params, atomic_amount, wallet_address, b""],
            )

            tx_hash = await wallet.send_transaction(to=checksum_morpho, data=call_data)
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(
                    f"Supply collateral transaction failed. Hash: {tx_hash}"
                )

            return (
                f"**Morpho Blue Supply Collateral**\n"
                f"Supplied: {amount} {symbol}\n"
                f"Market: {market_id}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Supply collateral failed: {e!s}")
