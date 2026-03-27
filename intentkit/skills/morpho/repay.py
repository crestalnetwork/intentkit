"""Morpho repay skill — repay borrowed assets in a Morpho Blue market."""

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
    MAX_UINT256,
    MORPHO_BLUE_ABI,
    MORPHO_BLUE_ADDRESS,
)


class RepayInput(BaseModel):
    """Input for Morpho Blue repay."""

    market_id: str = Field(description="Morpho Blue market ID (bytes32 hex string)")
    amount: str = Field(
        description="Amount to repay in whole units (e.g. '100'), or 'max' to repay full debt"
    )


class MorphoRepay(MorphoBaseTool):
    """Repay borrowed assets in a Morpho Blue market."""

    name: str = "morpho_repay"
    description: str = (
        "Repay borrowed assets in a Morpho Blue market. "
        "Use 'max' as amount to repay the full outstanding debt. "
        "Provide market_id (bytes32) and amount in whole units."
    )
    args_schema: ArgsSchema | None = RepayInput

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

            if amount.lower() == "max":
                # For max repay: use shares-based repay (assets=0, shares=borrowShares)
                morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)
                market_id_bytes = self._parse_market_id(market_id)
                position = await morpho.functions.position(
                    market_id_bytes, wallet_address
                ).call()
                _supply_shares, borrow_shares, _collateral = position
                if borrow_shares == 0:
                    return "No debt to repay in this market."
                atomic_amount = 0
                shares_amount = borrow_shares
                approve_amount = MAX_UINT256
                amount_display = "max"
            else:
                amount_decimal = Decimal(amount)
                if amount_decimal <= Decimal("0"):
                    raise ToolException("Error: Amount must be greater than 0")
                atomic_amount = int(amount_decimal * (10**decimals))
                shares_amount = 0
                approve_amount = atomic_amount
                amount_display = amount

            approve_data = token_contract.encode_abi(
                "approve", [checksum_morpho, approve_amount]
            )
            approve_tx = await wallet.send_transaction(to=loan_token, data=approve_data)
            receipt = await wallet.wait_for_receipt(approve_tx)
            if receipt.get("status", 0) != 1:
                raise ToolException(
                    f"Error: Approval transaction failed. Hash: {approve_tx}"
                )

            market_params = (loan_token, collateral_token, oracle, irm, lltv)

            morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)
            call_data = morpho.encode_abi(
                "repay",
                [market_params, atomic_amount, shares_amount, wallet_address, b""],
            )

            tx_hash = await wallet.send_transaction(to=checksum_morpho, data=call_data)
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Repay transaction failed. Hash: {tx_hash}")

            return (
                f"**Morpho Blue Repay**\n"
                f"Repaid: {amount_display} {symbol}\n"
                f"Market: {market_id}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Repay failed: {e!s}")
