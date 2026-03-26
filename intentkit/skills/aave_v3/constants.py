"""Aave V3 contract addresses and ABIs."""

from typing import Any

from intentkit.skills.erc20.constants import ERC20_ABI

# Network ID to chain ID mapping
NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "ethereum-mainnet": 1,
    "polygon-mainnet": 137,
    "arbitrum-mainnet": 42161,
    "optimism-mainnet": 10,
    "base-mainnet": 8453,
    "bnb-mainnet": 56,
}

# Aave V3 Pool (proxy) addresses per chain ID
POOL_ADDRESSES: dict[int, str] = {
    1: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
    137: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    42161: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    10: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    8453: "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
    56: "0x6807dc923806fE8Fd134338EABCA509979a7e0cB",
}

# Aave V3 Pool Data Provider addresses per chain ID
POOL_DATA_PROVIDER_ADDRESSES: dict[int, str] = {
    1: "0x0a16f2FCC0D44FaE41cc54e079281D84A363bECD",
    137: "0x243Aa95cAC2a25651eda86e80bEe66114413c43b",
    42161: "0x243Aa95cAC2a25651eda86e80bEe66114413c43b",
    10: "0x243Aa95cAC2a25651eda86e80bEe66114413c43b",
    8453: "0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A",
    56: "0xc90Df74A7c16245c5F5C5870327Ceb38Fe5d5328",
}

# Wrapped native token addresses per chain ID
WRAPPED_NATIVE_ADDRESSES: dict[int, str] = {
    1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    10: "0x4200000000000000000000000000000000000006",
    8453: "0x4200000000000000000000000000000000000006",
    56: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
}

# Native token symbols per chain ID
NATIVE_SYMBOLS: dict[int, str] = {
    1: "ETH",
    137: "MATIC",
    42161: "ETH",
    10: "ETH",
    8453: "ETH",
    56: "BNB",
}

# Max uint256 value (used for "max" withdraw/repay)
MAX_UINT256: int = 2**256 - 1

# Aave V3 Pool ABI (only functions we call)
POOL_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "referralCode", "type": "uint16"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "to", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "referralCode", "type": "uint16"},
            {"name": "onBehalfOf", "type": "address"},
        ],
        "name": "borrow",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
        ],
        "name": "repay",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "useAsCollateral", "type": "bool"},
        ],
        "name": "setUserUseReserveAsCollateral",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"name": "totalCollateralBase", "type": "uint256"},
            {"name": "totalDebtBase", "type": "uint256"},
            {"name": "availableBorrowsBase", "type": "uint256"},
            {"name": "currentLiquidationThreshold", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Aave V3 Pool Data Provider ABI (only functions we call)
POOL_DATA_PROVIDER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "getReserveData",
        "outputs": [
            {"name": "unbacked", "type": "uint256"},
            {"name": "accruedToTreasuryScaled", "type": "uint256"},
            {"name": "totalAToken", "type": "uint256"},
            {"name": "totalStableDebt", "type": "uint256"},
            {"name": "totalVariableDebt", "type": "uint256"},
            {"name": "liquidityRate", "type": "uint256"},
            {"name": "variableBorrowRate", "type": "uint256"},
            {"name": "stableBorrowRate", "type": "uint256"},
            {"name": "averageStableBorrowRate", "type": "uint256"},
            {"name": "liquidityIndex", "type": "uint256"},
            {"name": "variableBorrowIndex", "type": "uint256"},
            {"name": "lastUpdateTimestamp", "type": "uint40"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "getReserveConfigurationData",
        "outputs": [
            {"name": "decimals", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "liquidationThreshold", "type": "uint256"},
            {"name": "liquidationBonus", "type": "uint256"},
            {"name": "reserveFactor", "type": "uint256"},
            {"name": "usageAsCollateralEnabled", "type": "bool"},
            {"name": "borrowingEnabled", "type": "bool"},
            {"name": "stableBorrowRateEnabled", "type": "bool"},
            {"name": "isActive", "type": "bool"},
            {"name": "isFrozen", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

__all__ = [
    "NETWORK_TO_CHAIN_ID",
    "POOL_ADDRESSES",
    "POOL_DATA_PROVIDER_ADDRESSES",
    "WRAPPED_NATIVE_ADDRESSES",
    "NATIVE_SYMBOLS",
    "MAX_UINT256",
    "POOL_ABI",
    "POOL_DATA_PROVIDER_ABI",
    "ERC20_ABI",
]
