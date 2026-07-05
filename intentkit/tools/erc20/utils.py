"""Utility functions for ERC20 tools."""

from dataclasses import dataclass

from eth_abi.abi import decode
from web3 import AsyncWeb3, Web3

from intentkit.tools.erc20.constants import (
    ERC20_ABI,
    MULTICALL3_ABI,
    MULTICALL3_ADDRESS,
)


@dataclass
class TokenDetails:
    """Details about an ERC20 token."""

    name: str
    symbol: str
    decimals: int
    balance: int
    formatted_balance: str


async def get_token_details(
    w3: AsyncWeb3,
    contract_address: str,
    address: str,
) -> TokenDetails | None:
    """Get the details of an ERC20 token including name, symbol, decimals, and balance.

    Uses multicall to batch all requests into a single RPC call for efficiency.

    Args:
        w3: AsyncWeb3 client for the target network.
        contract_address: The contract address of the ERC20 token.
        address: The address to check the balance for.

    Returns:
        TokenDetails | None: Token details or None if there's an error.
    """
    try:
        checksum_contract = Web3.to_checksum_address(contract_address)
        checksum_check = Web3.to_checksum_address(address)

        # Create a local contract instance just to encode function calls
        encoder = Web3()
        contract = encoder.eth.contract(address=checksum_contract, abi=ERC20_ABI)

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

        # Execute multicall (read-only)
        multicall = w3.eth.contract(
            address=Web3.to_checksum_address(MULTICALL3_ADDRESS),
            abi=MULTICALL3_ABI,
        )
        results = await multicall.functions.aggregate3(calls).call()

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
    w3: AsyncWeb3,
    contract_address: str,
    address: str,
) -> TokenDetails | None:
    """Get the details of an ERC20 token using individual calls (fallback method).

    This is a simpler version that doesn't use multicall, useful for networks
    where multicall3 is not available.

    Args:
        w3: AsyncWeb3 client for the target network.
        contract_address: The contract address of the ERC20 token.
        address: The address to check the balance for.

    Returns:
        TokenDetails | None: Token details or None if there's an error.
    """
    try:
        checksum_contract = Web3.to_checksum_address(contract_address)
        checksum_check = Web3.to_checksum_address(address)

        contract = w3.eth.contract(address=checksum_contract, abi=ERC20_ABI)

        # Make individual calls
        name = await contract.functions.name().call()
        symbol = await contract.functions.symbol().call()
        decimals = await contract.functions.decimals().call()
        balance = await contract.functions.balanceOf(checksum_check).call()

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
    from intentkit.tools.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS

    network_tokens = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {})
    return network_tokens.get(symbol.upper())


def get_available_token_symbols(network_id: str) -> list[str]:
    """Get a list of available token symbols for a given network.

    Args:
        network_id: The network identifier (e.g., 'base-mainnet').

    Returns:
        List of available token symbols.
    """
    from intentkit.tools.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS

    network_tokens = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id, {})
    return list(network_tokens.keys())
