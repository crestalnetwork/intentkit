"""Shared helpers for PancakeSwap V3 skills."""

from decimal import Decimal
from typing import Any

from langchain_core.tools.base import ToolException
from web3 import Web3

from intentkit.skills.pancakeswap.constants import (
    ERC20_ABI,
    WRAPPED_NATIVE_ADDRESSES,
)


def resolve_token(token: str, chain_id: int) -> str:
    """Resolve 'native' keyword to wrapped native address."""
    if token.lower() == "native":
        addr = WRAPPED_NATIVE_ADDRESSES.get(chain_id)
        if not addr:
            raise ToolException(f"No wrapped native token for chain {chain_id}")
        return addr
    return token


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
    """Get ERC20 token symbol. Returns 'WBNB'/'WETH' for wrapped native."""
    wrapped = WRAPPED_NATIVE_ADDRESSES.get(chain_id, "").lower()
    if token_address.lower() == wrapped:
        return "WBNB" if chain_id == 56 else "WETH"
    try:
        symbol_abi = [
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=symbol_abi,
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
    """Check and set ERC20 allowance if needed."""
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
    """Convert raw integer amount to human-readable string."""
    return str(Decimal(raw) / Decimal(10**decimals))
