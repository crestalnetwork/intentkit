"""WOW buy token skill."""

import math

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field, field_validator
from web3 import Web3

from intentkit.skills.wow.base import WowBaseTool
from intentkit.skills.wow.constants import WOW_ABI
from intentkit.skills.wow.utils import get_buy_quote, get_has_graduated


class BuyTokenInput(BaseModel):
    """Input schema for buying WOW tokens."""

    contract_address: str = Field(..., description="The WOW token contract address")
    amount_eth_in_wei: str = Field(
        ...,
        description="Amount of ETH to spend (in wei). Must be a whole number string.",
        pattern=r"^\d+$",
    )

    @field_validator("contract_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate that the contract address is a valid Ethereum address."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)


class WowBuyToken(WowBaseTool):
    """Buy WOW tokens with ETH.

    This tool buys Zora WOW ERC20 memecoin tokens using ETH.
    """

    name: str = "wow_buy_token"
    description: str = """Buy a Zora WOW ERC20 memecoin (bonding curve token) with ETH.

This tool can only be used to buy a Zora WOW ERC20 memecoin. Do not use this tool
for any other purpose, or trading other assets.

Inputs:
- contract_address: The WOW token contract address
- amount_eth_in_wei: Amount of ETH to spend (in wei)

Important notes:
- The amount is a string and cannot have any decimal points, since the unit of measurement is wei
- Make sure to use the exact amount provided, and if there's any doubt, check by getting more information before continuing
- 1 wei = 0.000000000000000001 ETH
- Minimum purchase amount is 100000000000000 wei (0.0001 ETH)
"""
    args_schema: ArgsSchema | None = BuyTokenInput

    async def _arun(
        self,
        contract_address: str,
        amount_eth_in_wei: str,
    ) -> str:
        """Buy WOW tokens with ETH.

        Args:
            contract_address: The WOW token contract address.
            amount_eth_in_wei: Amount of ETH to spend (in wei).

        Returns:
            A message containing the purchase details or error message.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Validate minimum amount
            amount_wei = int(amount_eth_in_wei)
            if amount_wei < 100000000000000:  # 0.0001 ETH minimum
                return (
                    "Error: Amount too small. Minimum purchase amount is "
                    "100000000000000 wei (0.0001 ETH)."
                )

            # Check ETH balance
            eth_balance = await wallet.get_balance()
            if eth_balance < amount_wei:
                return (
                    f"Error: Insufficient ETH balance. "
                    f"Requested to spend {amount_eth_in_wei} wei, "
                    f"but only {eth_balance} wei available."
                )

            # Get buy quote
            token_quote = await get_buy_quote(
                wallet, contract_address, amount_eth_in_wei
            )

            if token_quote == 0:
                return (
                    "Error: Could not get buy quote for this token. "
                    "The token may not exist or there may be insufficient liquidity."
                )

            # Check if token has graduated to Uniswap
            has_graduated = await get_has_graduated(wallet, contract_address)

            # Calculate minimum tokens with 1% slippage
            min_tokens = math.floor(float(token_quote) * 0.99)

            # Encode buy function
            w3 = Web3()
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=WOW_ABI,
            )

            encoded_data = contract.encode_abi(
                "buy",
                [
                    wallet.address,  # recipient
                    wallet.address,  # refundRecipient
                    "0x0000000000000000000000000000000000000000",  # orderReferrer
                    "",  # comment
                    1 if has_graduated else 0,  # expectedMarketType
                    min_tokens,  # minOrderSize
                    0,  # sqrtPriceLimitX96
                ],
            )

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=Web3.to_checksum_address(contract_address),
                value=amount_wei,
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
                f"Successfully purchased WOW ERC20 memecoin.\n"
                f"Spent: {amount_eth_in_wei} wei ({int(amount_eth_in_wei) / 10**18:.6f} ETH)\n"
                f"Expected tokens: ~{token_quote} (minimum: {min_tokens})\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error buying Zora WOW ERC20 memecoin: {e!s}"
