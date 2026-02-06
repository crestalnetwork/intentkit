"""Constants for WETH skills."""

from typing import Any

from intentkit.skills.erc20.constants import ERC20_ABI, TOKEN_ADDRESSES_BY_SYMBOLS

WETH_ABI: list[dict[str, Any]] = [
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "name": "wad",
                "type": "uint256",
            },
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "name": "account",
                "type": "address",
            },
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "type": "uint256",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_weth_address(network_id: str) -> str | None:
    """Get the WETH address for the given network.

    Args:
        network_id: The network identifier (e.g., 'base-mainnet').

    Returns:
        The WETH address for the network, or None if not supported.
    """
    network_tokens = TOKEN_ADDRESSES_BY_SYMBOLS.get(network_id)
    return network_tokens.get("WETH") if network_tokens else None


# Re-export ERC20_ABI for convenience
__all__ = ["WETH_ABI", "ERC20_ABI", "get_weth_address"]
