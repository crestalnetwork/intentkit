"""PancakeSwap V3 quote skill — get swap price via QuoterV2 contract."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.pancakeswap.base import PancakeSwapBaseTool
from intentkit.skills.pancakeswap.constants import (
    FEE_TIERS,
    NETWORK_TO_CHAIN_ID,
    QUOTER_V2_ABI,
    QUOTER_V2_ADDRESSES,
)
from intentkit.skills.pancakeswap.utils import get_decimals, resolve_token

NAME = "pancakeswap_quote"


class PancakeSwapQuoteInput(BaseModel):
    """Input for PancakeSwap quote."""

    token_in: str = Field(
        description="Input token address, or 'native' for native token"
    )
    token_out: str = Field(
        description="Output token address, or 'native' for native token"
    )
    amount: str = Field(
        description="Amount to swap in human-readable format (e.g. '1.5')"
    )


class PancakeSwapQuote(PancakeSwapBaseTool):
    """Get a PancakeSwap V3 swap quote."""

    name: str = NAME
    description: str = (
        "Get a PancakeSwap V3 swap quote. Returns expected output amount. "
        "Provide token contract addresses and amount in human-readable format."
    )
    args_schema: ArgsSchema | None = PancakeSwapQuoteInput

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
                    f"PancakeSwap not supported on {network_id}. "
                    f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
                )

            quoter_address = QUOTER_V2_ADDRESSES.get(chain_id)
            if not quoter_address:
                raise ToolException(f"No QuoterV2 address for chain {chain_id}")

            w3 = self.web3_client()

            # Resolve native token to wrapped address
            addr_in = resolve_token(token_in, chain_id)
            addr_out = resolve_token(token_out, chain_id)

            # Get token decimals
            decimals_in = await get_decimals(w3, addr_in, chain_id)
            decimals_out = await get_decimals(w3, addr_out, chain_id)

            # Convert human-readable amount to raw
            amount_raw = int(Decimal(amount) * Decimal(10**decimals_in))
            if amount_raw <= 0:
                raise ToolException("Amount must be positive")

            # Try all fee tiers, pick best output
            quoter = w3.eth.contract(
                address=Web3.to_checksum_address(quoter_address),
                abi=QUOTER_V2_ABI,
            )

            best_out = 0
            best_fee = 0
            best_gas = 0

            for fee in FEE_TIERS:
                try:
                    result = await quoter.functions.quoteExactInputSingle(
                        (
                            Web3.to_checksum_address(addr_in),
                            Web3.to_checksum_address(addr_out),
                            amount_raw,
                            fee,
                            0,  # sqrtPriceLimitX96 = 0 means no limit
                        )
                    ).call()
                    amount_out = result[0]
                    gas_estimate = result[3]
                    if amount_out > best_out:
                        best_out = amount_out
                        best_fee = fee
                        best_gas = gas_estimate
                except Exception:
                    continue

            if best_out == 0:
                raise ToolException(
                    "No liquidity found for this pair on PancakeSwap V3."
                )

            # Format output
            out_human = Decimal(best_out) / Decimal(10**decimals_out)
            fee_pct = Decimal(best_fee) / Decimal(10000)

            return (
                f"**PancakeSwap V3 Quote**\n"
                f"Input: {amount} (decimals: {decimals_in})\n"
                f"Output: {out_human:.8f} (decimals: {decimals_out})\n"
                f"Fee tier: {fee_pct}%\n"
                f"Gas estimate: {best_gas}\n"
                f"Use pancakeswap_swap to execute this trade."
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Quote failed: {e!s}")
