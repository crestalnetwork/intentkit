"""Morpho borrow skill — borrow assets from a Morpho Blue market."""

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


class BorrowInput(BaseModel):
    """Input for Morpho Blue borrow."""

    market_id: str = Field(description="Morpho Blue market ID (bytes32 hex string)")
    amount: str = Field(
        description="Amount to borrow in whole units (e.g. '1000' for 1000 USDC)"
    )


class MorphoBorrow(MorphoBaseTool):
    """Borrow assets from a Morpho Blue market against supplied collateral."""

    name: str = "morpho_borrow"
    description: str = (
        "Borrow assets from a Morpho Blue market against your collateral. "
        "You must have sufficient collateral supplied to the market. "
        "Provide market_id (bytes32) and amount in whole units."
    )
    args_schema: ArgsSchema | None = BorrowInput

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
                address=Web3.to_checksum_address(loan_token), abi=ERC20_ABI
            )
            decimals, symbol = await asyncio.gather(
                token_contract.functions.decimals().call(),
                token_contract.functions.symbol().call(),
            )

            amount_decimal = Decimal(amount)
            if amount_decimal <= Decimal("0"):
                raise ToolException("Error: Amount must be greater than 0")
            atomic_amount = int(amount_decimal * (10**decimals))

            market_params = (loan_token, collateral_token, oracle, irm, lltv)

            morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)
            call_data = morpho.encode_abi(
                "borrow",
                [market_params, atomic_amount, 0, wallet_address, wallet_address],
            )

            tx_hash = await wallet.send_transaction(to=checksum_morpho, data=call_data)
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Borrow transaction failed. Hash: {tx_hash}")

            return (
                f"**Morpho Blue Borrow**\n"
                f"Borrowed: {amount} {symbol}\n"
                f"Market: {market_id}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Borrow failed: {e!s}")
