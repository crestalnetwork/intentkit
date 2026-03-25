"""Aerodrome Slipstream swap skill — execute a token swap via SwapRouter."""

import time
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aerodrome.base import AerodromeBaseTool
from intentkit.skills.aerodrome.constants import (
    NETWORK_TO_CHAIN_ID,
    QUOTER_V2_ABI,
    QUOTER_V2_ADDRESS,
    SWAP_ROUTER_ABI,
    SWAP_ROUTER_ADDRESS,
    TICK_SPACINGS,
)
from intentkit.skills.aerodrome.utils import (
    convert_amount,
    ensure_allowance,
    get_decimals,
    resolve_token,
)

NAME = "aerodrome_swap"


class AerodromeSwapInput(BaseModel):
    """Input for Aerodrome swap."""

    token_in: str = Field(
        description="Input token address, or 'native' for ETH on Base"
    )
    token_out: str = Field(
        description="Output token address, or 'native' for ETH on Base"
    )
    amount: str = Field(
        description="Amount to swap in human-readable format (e.g. '1.5')"
    )
    slippage: float = Field(
        default=0.5,
        description="Slippage tolerance in percent (e.g. 0.5 for 0.5%)",
    )


class AerodromeSwap(AerodromeBaseTool):
    """Execute an Aerodrome Slipstream token swap on Base."""

    name: str = NAME
    description: str = (
        "Execute a token swap on Aerodrome Slipstream (Base). "
        "Handles ERC20 approval automatically. "
        "Provide token contract addresses and amount in human-readable format."
    )
    args_schema: ArgsSchema | None = AerodromeSwapInput

    @override
    async def _arun(
        self,
        token_in: str,
        token_out: str,
        amount: str,
        slippage: float = 0.5,
        **kwargs: Any,
    ) -> str:
        try:
            network_id = self.get_agent_network_id()
            if not network_id:
                raise ToolException("Agent network_id is not configured")

            chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
            if not chain_id:
                raise ToolException(
                    f"Aerodrome is only supported on Base. "
                    f"Current network: {network_id}"
                )

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()

            is_native_in = token_in.lower() == "native"
            addr_in = resolve_token(token_in)
            addr_out = resolve_token(token_out)

            decimals_in = await get_decimals(w3, addr_in)
            decimals_out = await get_decimals(w3, addr_out)

            amount_raw = convert_amount(amount, decimals_in)

            quoter = w3.eth.contract(
                address=Web3.to_checksum_address(QUOTER_V2_ADDRESS),
                abi=QUOTER_V2_ABI,
            )

            best_out = 0
            best_tick_spacing = 0

            for tick_spacing in TICK_SPACINGS:
                try:
                    result = await quoter.functions.quoteExactInputSingle(
                        (
                            Web3.to_checksum_address(addr_in),
                            Web3.to_checksum_address(addr_out),
                            amount_raw,
                            tick_spacing,
                            0,
                        )
                    ).call()
                    if result[0] > best_out:
                        best_out = result[0]
                        best_tick_spacing = tick_spacing
                except Exception:
                    continue

            if best_out == 0:
                return "No liquidity found for this pair on Aerodrome Slipstream."

            # Calculate minimum output with slippage
            slippage_factor = Decimal(1) - Decimal(str(slippage)) / Decimal(100)
            amount_out_min = int(Decimal(best_out) * slippage_factor)

            checksum_router = Web3.to_checksum_address(SWAP_ROUTER_ADDRESS)
            checksum_in = Web3.to_checksum_address(addr_in)
            checksum_out = Web3.to_checksum_address(addr_out)
            recipient = Web3.to_checksum_address(wallet.address)
            deadline = int(time.time()) + 600  # 10 minutes

            # Approve ERC20 if not native
            if not is_native_in:
                await ensure_allowance(
                    w3, wallet, checksum_in, checksum_router, amount_raw
                )

            # Build swap calldata
            router_contract = w3.eth.contract(
                address=checksum_router,
                abi=SWAP_ROUTER_ABI,
            )
            swap_data = router_contract.encode_abi(
                "exactInputSingle",
                [
                    (
                        checksum_in,
                        checksum_out,
                        best_tick_spacing,
                        recipient,
                        deadline,
                        amount_raw,
                        amount_out_min,
                        0,  # sqrtPriceLimitX96 = 0
                    )
                ],
            )

            # Send transaction
            tx_value = amount_raw if is_native_in else 0
            tx_hash = await wallet.send_transaction(
                to=checksum_router,
                data=swap_data,
                value=tx_value,
            )

            # Wait for confirmation
            receipt = await wallet.wait_for_receipt(tx_hash)
            status = receipt.get("status", 0)
            if status != 1:
                raise ToolException(f"Swap transaction failed. Hash: {tx_hash}")

            out_human = Decimal(best_out) / Decimal(10**decimals_out)
            min_human = Decimal(amount_out_min) / Decimal(10**decimals_out)

            return (
                f"**Swap Executed**\n"
                f"Sent: {amount} (token: {token_in})\n"
                f"Expected: ~{out_human:.8f} (token: {token_out})\n"
                f"Minimum: {min_human:.8f} (slippage: {slippage}%)\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Swap failed: {e!s}")
