"""WOW sell token skill."""

import math

from pydantic import BaseModel, Field, field_validator
from web3 import Web3

from intentkit.skills.wow.base import WowBaseTool
from intentkit.skills.wow.constants import WOW_ABI
from intentkit.skills.wow.utils import (
    get_has_graduated,
    get_sell_quote,
    get_token_balance,
)


class SellTokenInput(BaseModel):
    """Input schema for selling WOW tokens."""

    contract_address: str = Field(..., description="The WOW token contract address")
    amount_tokens_in_wei: str = Field(
        ...,
        description="Amount of tokens to sell (in wei). Must be a whole number string.",
        pattern=r"^\d+$",
    )

    @field_validator("contract_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate that the contract address is a valid Ethereum address."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)


class WowSellToken(WowBaseTool):
    """Sell WOW tokens for ETH.

    This tool sells Zora WOW ERC20 memecoin tokens for ETH.
    """

    name: str = "wow_sell_token"
    description: str = """Sell a Zora WOW ERC20 memecoin (bonding curve token) for ETH.

This tool can only be used to sell a Zora WOW ERC20 memecoin. Do not use this tool
for any other purpose, or trading other assets.

Inputs:
- contract_address: The WOW token contract address
- amount_tokens_in_wei: Amount of tokens to sell (in wei)

Important notes:
- The amount is a string and cannot have any decimal points, since the unit of measurement is wei
- Make sure to use the exact amount provided, and if there's any doubt, check by getting more information before continuing
- 1 wei = 0.000000000000000001 of the token
- Minimum sale amount to account for slippage is 100000000000000 wei (0.0001 tokens)
"""
    args_schema: type[BaseModel] = SellTokenInput

    async def _arun(
        self,
        contract_address: str,
        amount_tokens_in_wei: str,
    ) -> str:
        """Sell WOW tokens for ETH.

        Args:
            contract_address: The WOW token contract address.
            amount_tokens_in_wei: Amount of tokens to sell (in wei).

        Returns:
            A message containing the sell details or error message.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            amount_tokens = int(amount_tokens_in_wei)

            # Check token balance
            token_balance = await get_token_balance(wallet, contract_address)
            if token_balance < amount_tokens:
                return (
                    f"Error: Insufficient token balance. "
                    f"Requested to sell {amount_tokens_in_wei} wei, "
                    f"but only {token_balance} wei available."
                )

            # Get sell quote
            eth_quote = await get_sell_quote(
                wallet, contract_address, amount_tokens_in_wei
            )

            if eth_quote == 0:
                return (
                    "Error: Could not get sell quote for this token. "
                    "The token may not exist or there may be insufficient liquidity."
                )

            # Check if token has graduated to Uniswap
            has_graduated = await get_has_graduated(wallet, contract_address)

            # Calculate minimum ETH with 2% slippage
            min_eth = math.floor(float(eth_quote) * 0.98)

            # Encode sell function
            w3 = Web3()
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=WOW_ABI,
            )

            encoded_data = contract.encode_abi(
                "sell",
                [
                    amount_tokens,  # tokensToSell
                    wallet.address,  # recipient
                    "0x0000000000000000000000000000000000000000",  # orderReferrer
                    "",  # comment
                    1 if has_graduated else 0,  # expectedMarketType
                    min_eth,  # minPayoutSize
                    0,  # sqrtPriceLimitX96
                ],
            )

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=Web3.to_checksum_address(contract_address),
                data=encoded_data,
            )

            # Wait for receipt
            receipt = await wallet.wait_for_transaction_receipt(tx_hash)

            if receipt.get("status") == 0:
                return (
                    f"Transaction failed with hash: {tx_hash}. "
                    "The transaction failed to execute. This could be due to "
                    "slippage or insufficient liquidity."
                )

            return (
                f"Successfully sold WOW ERC20 memecoin.\n"
                f"Sold: {amount_tokens_in_wei} wei tokens\n"
                f"Expected ETH: ~{eth_quote} wei ({eth_quote / 10**18:.6f} ETH)\n"
                f"Minimum ETH (with slippage): {min_eth} wei\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error selling Zora WOW ERC20 memecoin: {e!s}"
