"""Shared helpers for Aave V3 skills."""

from decimal import Decimal
from typing import Any

from langchain_core.tools.base import ToolException
from web3 import Web3

from intentkit.skills.aave_v3.constants import (
    ERC20_ABI,
    MAX_UINT256,
    NATIVE_SYMBOLS,
    WRAPPED_NATIVE_ADDRESSES,
)


async def get_decimals(w3: Any, token_address: str, chain_id: int) -> int:
    """Get ERC20 token decimals. Returns 18 for wrapped native tokens."""
    wrapped = WRAPPED_NATIVE_ADDRESSES.get(chain_id, "").lower()
    if token_address.lower() == wrapped:
        return 18
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        return await contract.functions.decimals().call()
    except Exception:
        return 18


async def get_token_symbol(w3: Any, token_address: str, chain_id: int) -> str:
    """Get ERC20 token symbol. Returns native symbol for wrapped native."""
    wrapped = WRAPPED_NATIVE_ADDRESSES.get(chain_id, "").lower()
    if token_address.lower() == wrapped:
        return f"W{NATIVE_SYMBOLS.get(chain_id, 'ETH')}"
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        return await contract.functions.symbol().call()
    except Exception:
        return token_address[:10] + "..."


async def ensure_allowance(
    w3: Any,
    wallet: Any,
    token_address: str,
    spender: str,
    amount: int,
) -> None:
    """Check and set ERC20 allowance if needed.

    Handles USDT-style tokens that require resetting allowance to 0 first.
    """
    contract = w3.eth.contract(
        address=token_address,
        abi=ERC20_ABI,
    )
    current = await contract.functions.allowance(
        Web3.to_checksum_address(wallet.address),
        spender,
    ).call()

    if current >= amount:
        return

    # Some tokens (e.g. USDT) revert if changing non-zero allowance directly
    if current > 0:
        reset_data = contract.encode_abi("approve", [spender, 0])
        reset_tx = await wallet.send_transaction(to=token_address, data=reset_data)
        await wallet.wait_for_receipt(reset_tx)

    approve_data = contract.encode_abi("approve", [spender, amount])
    tx_hash = await wallet.send_transaction(
        to=token_address,
        data=approve_data,
    )
    await wallet.wait_for_receipt(tx_hash)


def convert_amount(amount: str, decimals: int) -> int:
    """Convert human-readable amount to raw integer."""
    raw = int(Decimal(amount) * Decimal(10**decimals))
    if raw <= 0:
        raise ToolException("Amount must be positive")
    return raw


def format_amount(raw: int, decimals: int) -> str:
    """Convert raw integer back to human-readable string."""
    return str(Decimal(raw) / Decimal(10**decimals))


def format_health_factor(raw: int) -> str:
    """Format Aave health factor (18 decimals) to human-readable."""
    if raw == MAX_UINT256:
        return "∞ (no borrows)"
    value = Decimal(raw) / Decimal(10**18)
    return f"{value:.4f}"


def format_ray(raw: int) -> str:
    """Format Aave RAY value (27 decimals) to percentage string."""
    value = Decimal(raw) / Decimal(10**27) * Decimal(100)
    return f"{value:.2f}%"


def format_base_currency(raw: int) -> str:
    """Format Aave base currency value (8 decimals USD) to human-readable."""
    value = Decimal(raw) / Decimal(10**8)
    return f"${value:,.2f}"
