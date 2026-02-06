"""Utility functions for ERC20 skills."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from eth_abi.abi import decode
from web3 import Web3

from intentkit.skills.erc20.constants import (
    ERC20_ABI,
    MULTICALL3_ABI,
    MULTICALL3_ADDRESS,
)

if TYPE_CHECKING:
    from intentkit.wallets.evm_wallet import EvmWallet


@dataclass
class TokenDetails:
    """Details about an ERC20 token."""

    name: str
    symbol: str
    decimals: int
    balance: int
    formatted_balance: str


async def get_token_details(
    wallet: "EvmWallet",
    contract_address: str,
    address: str | None = None,
) -> TokenDetails | None:
    """Get the details of an ERC20 token including name, symbol, decimals, and balance.

    Uses multicall to batch all requests into a single RPC call for efficiency.

    Args:
        wallet: The unified wallet instance.
        contract_address: The contract address of the ERC20 token.
        address: The address to check the balance for. If not provided, uses the wallet's address.

    Returns:
        TokenDetails | None: Token details or None if there's an error.
    """
    try:
        w3 = Web3()
        check_address = address if address else wallet.address
        checksum_contract = w3.to_checksum_address(contract_address)
        checksum_check = w3.to_checksum_address(check_address)

        # Create the contract instance to encode function calls
        contract = w3.eth.contract(address=checksum_contract, abi=ERC20_ABI)

        # Encode the four function calls
        name_data = contract.encode_abi("name", [])
        symbol_data = contract.encode_abi("symbol", [])
        decimals_data = contract.encode_abi("decimals", [])
        balance_data = contract.encode_abi("balanceOf", [checksum_check])

        # Prepare multicall calls
        calls = [
            (checksum_contract, True, name_data),
            (checksum_contract, True, symbol_data),
            (checksum_contract, True, decimals_data),
            (checksum_contract, True, balance_data),
        ]

        # Execute multicall
        checksum_multicall = w3.to_checksum_address(MULTICALL3_ADDRESS)
        results = await wallet.call_contract(
            contract_address=checksum_multicall,
            abi=MULTICALL3_ABI,
            function_name="aggregate3",
            args=[calls],
        )

        # Decode results
        if not results or len(results) != 4:
            return None

        # Check if all calls succeeded and returned data
        for success, return_data in results:
            if not success or len(return_data) == 0:
                # This is expected for non-ERC20 contracts/EOAs
                return None

        # Decode each result using eth_abi
        name = decode(["string"], results[0][1])[0]
        symbol = decode(["string"], results[1][1])[0]
        decimals = decode(["uint8"], results[2][1])[0]
        balance = decode(["uint256"], results[3][1])[0]

        # Format balance
        formatted_balance = str(balance / (10**decimals))

        return TokenDetails(
            name=name,
            symbol=symbol,
            decimals=decimals,
            balance=balance,
            formatted_balance=formatted_balance,
        )
    except Exception:
        return None


async def get_token_details_simple(
    wallet: "EvmWallet",
    contract_address: str,
    address: str | None = None,
) -> TokenDetails | None:
    """Get the details of an ERC20 token using individual calls (fallback method).

    This is a simpler version that doesn't use multicall, useful for networks
    where multicall3 is not available.

    Args:
        wallet: The unified wallet instance.
        contract_address: The contract address of the ERC20 token.
        address: The address to check the balance for. If not provided, uses the wallet's address.

    Returns:
        TokenDetails | None: Token details or None if there's an error.
    """
    try:
        w3 = Web3()
        check_address = address if address else wallet.address
        checksum_contract = w3.to_checksum_address(contract_address)
        checksum_check = w3.to_checksum_address(check_address)

        # Make individual calls
        name = await wallet.call_contract(
            contract_address=checksum_contract,
            abi=ERC20_ABI,
            function_name="name",
            args=[],
        )

        symbol = await wallet.call_contract(
            contract_address=checksum_contract,
            abi=ERC20_ABI,
            function_name="symbol",
            args=[],
        )

        decimals = await wallet.call_contract(
            contract_address=checksum_contract,
            abi=ERC20_ABI,
            function_name="decimals",
            args=[],
        )

        balance = await wallet.call_contract(
            contract_address=checksum_contract,
            abi=ERC20_ABI,
            function_name="balanceOf",
            args=[checksum_check],
        )

        # Format balance
        formatted_balance = str(balance / (10**decimals))

        return TokenDetails(
            name=name,
            symbol=symbol,
            decimals=decimals,
            balance=balance,
            formatted_balance=formatted_balance,
        )
    except Exception:
        return None


def get_token_address_by_symbol(network_id: str, symbol: str) -> str | None:
    """Get a token contract address by its symbol for a given network.

    Args:
        network_id: The network identifier (e.g., 'base-mainnet').
        symbol: The token symbol (e.g., 'USDC').

    Returns:
        The token contract address or None if not found.
    """
    from intentkit.skills.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS

    network_tokens = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {})
    return network_tokens.get(symbol.upper())


def get_available_token_symbols(network_id: str) -> list[str]:
    """Get a list of available token symbols for a given network.

    Args:
        network_id: The network identifier (e.g., 'base-mainnet').

    Returns:
        List of available token symbols.
    """
    from intentkit.skills.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS

    network_tokens = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {})
    return list(network_tokens.keys())
