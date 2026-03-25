"""Aerodrome Slipstream quote skill — get swap price via QuoterV2 contract."""

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
    TICK_SPACINGS,
)
from intentkit.skills.aerodrome.utils import convert_amount, get_decimals, resolve_token

NAME = "aerodrome_quote"


class AerodromeQuoteInput(BaseModel):
    """Input for Aerodrome quote."""

    token_in: str = Field(
        description="Input token address, or 'native' for ETH on Base"
    )
    token_out: str = Field(
        description="Output token address, or 'native' for ETH on Base"
    )
    amount: str = Field(
        description="Amount to swap in human-readable format (e.g. '1.5')"
    )


class AerodromeQuote(AerodromeBaseTool):
    """Get an Aerodrome Slipstream swap quote."""

    name: str = NAME
    description: str = (
        "Get an Aerodrome Slipstream swap quote on Base. Returns expected output amount. "
        "Provide token contract addresses and amount in human-readable format."
    )
    args_schema: ArgsSchema | None = AerodromeQuoteInput

    @override
    async def _arun(
        self,
        token_in: str,
        token_out: str,
        amount: str,
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

            w3 = self.web3_client()

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
            best_gas = 0

            for tick_spacing in TICK_SPACINGS:
                try:
                    result = await quoter.functions.quoteExactInputSingle(
                        (
                            Web3.to_checksum_address(addr_in),
                            Web3.to_checksum_address(addr_out),
                            amount_raw,
                            tick_spacing,
                            0,  # sqrtPriceLimitX96 = 0 means no limit
                        )
                    ).call()
                    amount_out = result[0]
                    gas_estimate = result[3]
                    if amount_out > best_out:
                        best_out = amount_out
                        best_tick_spacing = tick_spacing
                        best_gas = gas_estimate
                except Exception:
                    continue

            if best_out == 0:
                return "No liquidity found for this pair on Aerodrome Slipstream."

            # Format output
            out_human = Decimal(best_out) / Decimal(10**decimals_out)

            return (
                f"**Aerodrome Slipstream Quote**\n"
                f"Input: {amount} (decimals: {decimals_in})\n"
                f"Output: {out_human:.8f} (decimals: {decimals_out})\n"
                f"Tick spacing: {best_tick_spacing}\n"
                f"Gas estimate: {best_gas}\n"
                f"Use aerodrome_swap to execute this trade."
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Quote failed: {e!s}")
