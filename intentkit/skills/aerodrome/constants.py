"""Aerodrome Slipstream (CL) contract addresses and ABIs on Base."""

from typing import Any

# Shared skill name for cross-skill persistent data (skill data is scoped by skill name)
SKILL_DATA_NAMESPACE: str = "aerodrome"
STAKED_DATA_KEY: str = "staked_token_ids"

# Aerodrome is Base-only (chain ID 8453)
CHAIN_ID: int = 8453

# Network ID mapping
NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "base-mainnet": 8453,
}

# WETH on Base
WRAPPED_NATIVE_ADDRESS: str = "0x4200000000000000000000000000000000000006"

# AERO token address
AERO_TOKEN_ADDRESS: str = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"

# Aerodrome Slipstream contract addresses (Base)
QUOTER_V2_ADDRESS: str = "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0"
SWAP_ROUTER_ADDRESS: str = "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5"
POSITION_MANAGER_ADDRESS: str = "0x827922686190790b37229fd06084350E74485b72"
CL_FACTORY_ADDRESS: str = "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A"
VOTER_ADDRESS: str = "0x16613524e02ad97eDfeF371bC883F2F5d6C480A5"

# Supported tick spacings (Aerodrome uses tickSpacing directly, not fee tiers)
TICK_SPACINGS: list[int] = [1, 50, 100, 200]

# Full-range tick bounds
MIN_TICK: int = -887272
MAX_TICK: int = 887272

# QuoterV2 ABI - quoteExactInputSingle (uses tickSpacing instead of fee)
QUOTER_V2_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "tickSpacing", "type": "int24"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# SwapRouter ABI - exactInputSingle (uses tickSpacing, has deadline)
SWAP_ROUTER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "tickSpacing", "type": "int24"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

# WETH deposit ABI (for wrapping native ETH)
WETH_DEPOSIT_ABI: list[dict[str, Any]] = [
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]

# Minimal ERC20 ABI for approve and allowance
ERC20_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# NonfungiblePositionManager ABI (uses tickSpacing instead of fee, has sqrtPriceX96 in mint)
POSITION_MANAGER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "token0", "type": "address"},
                    {"name": "token1", "type": "address"},
                    {"name": "tickSpacing", "type": "int24"},
                    {"name": "tickLower", "type": "int24"},
                    {"name": "tickUpper", "type": "int24"},
                    {"name": "amount0Desired", "type": "uint256"},
                    {"name": "amount1Desired", "type": "uint256"},
                    {"name": "amount0Min", "type": "uint256"},
                    {"name": "amount1Min", "type": "uint256"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "sqrtPriceX96", "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "mint",
        "outputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "liquidity", "type": "uint128"},
                    {"name": "amount0Min", "type": "uint256"},
                    {"name": "amount1Min", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "decreaseLiquidity",
        "outputs": [
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amount0Max", "type": "uint128"},
                    {"name": "amount1Max", "type": "uint128"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "collect",
        "outputs": [
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "burn",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "tickSpacing", "type": "int24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "index", "type": "uint256"},
        ],
        "name": "tokenOfOwnerByIndex",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# CLFactory ABI (uses tickSpacing instead of fee)
CL_FACTORY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "tickSpacing", "type": "int24"},
        ],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Voter ABI (to look up gauge for a pool)
VOTER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "pool", "type": "address"}],
        "name": "gauges",
        "outputs": [{"name": "gauge", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# CLGauge ABI (for staking LP NFTs to earn AERO rewards)
CL_GAUGE_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "earned",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getReward",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "depositor", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "stakedContains",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]
