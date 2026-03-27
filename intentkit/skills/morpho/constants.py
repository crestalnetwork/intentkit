"""Constants for Morpho skills."""

from intentkit.skills.erc20.constants import ERC20_ABI

# Supported networks for Morpho
SUPPORTED_NETWORKS = ["base-mainnet", "base-sepolia"]

# Morpho Blue contract address (same on all deployed chains)
MORPHO_BLUE_ADDRESS = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"

MAX_UINT256 = 2**256 - 1

# MarketParams tuple component type used in ABI
_MARKET_PARAMS_TUPLE = {
    "components": [
        {"internalType": "address", "name": "loanToken", "type": "address"},
        {"internalType": "address", "name": "collateralToken", "type": "address"},
        {"internalType": "address", "name": "oracle", "type": "address"},
        {"internalType": "address", "name": "irm", "type": "address"},
        {"internalType": "uint256", "name": "lltv", "type": "uint256"},
    ],
    "internalType": "struct MarketParams",
    "name": "marketParams",
    "type": "tuple",
}

# --- MetaMorpho Vault ABI ---

METAMORPHO_ABI: list[dict] = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "address", "name": "receiver", "type": "address"},
        ],
        "name": "deposit",
        "outputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "address", "name": "owner", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "asset",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "shares", "type": "uint256"},
        ],
        "name": "convertToAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# --- Morpho Blue ABI ---

MORPHO_BLUE_ABI: list[dict] = [
    # idToMarketParams
    {
        "inputs": [{"internalType": "Id", "name": "id", "type": "bytes32"}],
        "name": "idToMarketParams",
        "outputs": [
            {"internalType": "address", "name": "loanToken", "type": "address"},
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "address", "name": "oracle", "type": "address"},
            {"internalType": "address", "name": "irm", "type": "address"},
            {"internalType": "uint256", "name": "lltv", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # position
    {
        "inputs": [
            {"internalType": "Id", "name": "id", "type": "bytes32"},
            {"internalType": "address", "name": "user", "type": "address"},
        ],
        "name": "position",
        "outputs": [
            {"internalType": "uint256", "name": "supplyShares", "type": "uint256"},
            {"internalType": "uint128", "name": "borrowShares", "type": "uint128"},
            {"internalType": "uint128", "name": "collateral", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # market
    {
        "inputs": [{"internalType": "Id", "name": "id", "type": "bytes32"}],
        "name": "market",
        "outputs": [
            {"internalType": "uint128", "name": "totalSupplyAssets", "type": "uint128"},
            {"internalType": "uint128", "name": "totalSupplyShares", "type": "uint128"},
            {"internalType": "uint128", "name": "totalBorrowAssets", "type": "uint128"},
            {"internalType": "uint128", "name": "totalBorrowShares", "type": "uint128"},
            {"internalType": "uint128", "name": "lastUpdate", "type": "uint128"},
            {"internalType": "uint128", "name": "fee", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # supplyCollateral
    {
        "inputs": [
            _MARKET_PARAMS_TUPLE,
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "address", "name": "onBehalf", "type": "address"},
            {"internalType": "bytes", "name": "data", "type": "bytes"},
        ],
        "name": "supplyCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdrawCollateral
    {
        "inputs": [
            _MARKET_PARAMS_TUPLE,
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "address", "name": "onBehalf", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
        ],
        "name": "withdrawCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # borrow
    {
        "inputs": [
            _MARKET_PARAMS_TUPLE,
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "uint256", "name": "shares", "type": "uint256"},
            {"internalType": "address", "name": "onBehalf", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
        ],
        "name": "borrow",
        "outputs": [
            {"internalType": "uint256", "name": "assetsBorrowed", "type": "uint256"},
            {"internalType": "uint256", "name": "sharesBorrowed", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # repay
    {
        "inputs": [
            _MARKET_PARAMS_TUPLE,
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "uint256", "name": "shares", "type": "uint256"},
            {"internalType": "address", "name": "onBehalf", "type": "address"},
            {"internalType": "bytes", "name": "data", "type": "bytes"},
        ],
        "name": "repay",
        "outputs": [
            {"internalType": "uint256", "name": "assetsRepaid", "type": "uint256"},
            {"internalType": "uint256", "name": "sharesRepaid", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Re-export ERC20_ABI for convenience
__all__ = [
    "METAMORPHO_ABI",
    "MORPHO_BLUE_ABI",
    "MORPHO_BLUE_ADDRESS",
    "ERC20_ABI",
    "SUPPORTED_NETWORKS",
    "MAX_UINT256",
]
