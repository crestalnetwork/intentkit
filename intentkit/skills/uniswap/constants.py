"""Uniswap V3 contract addresses and ABIs."""

from typing import Any

# Uniswap V3 QuoterV2 addresses per chain ID
QUOTER_V2_ADDRESSES: dict[int, str] = {
    1: "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",  # Ethereum
    42161: "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",  # Arbitrum
    10: "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",  # Optimism
    137: "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",  # Polygon
    8453: "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",  # Base
}

# Uniswap V3 SwapRouter02 addresses per chain ID
SWAP_ROUTER_ADDRESSES: dict[int, str] = {
    1: "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Ethereum
    42161: "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Arbitrum
    10: "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Optimism
    137: "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Polygon
    8453: "0x2626664c2603336E57B271c5C0b26F421741e481",  # Base
}

# Wrapped native token addresses per chain ID
WRAPPED_NATIVE_ADDRESSES: dict[int, str] = {
    1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH (Ethereum)
    42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH (Arbitrum)
    10: "0x4200000000000000000000000000000000000006",  # WETH (Optimism)
    137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC (Polygon)
    8453: "0x4200000000000000000000000000000000000006",  # WETH (Base)
}

# Uniswap V3 NonfungiblePositionManager addresses per chain ID
POSITION_MANAGER_ADDRESSES: dict[int, str] = {
    1: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Ethereum
    42161: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Arbitrum
    10: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Optimism
    137: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Polygon
    8453: "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",  # Base
}

# Uniswap V3 Factory addresses per chain ID
FACTORY_ADDRESSES: dict[int, str] = {
    1: "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # Ethereum
    42161: "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # Arbitrum
    10: "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # Optimism
    137: "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # Polygon
    8453: "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",  # Base
}

# Common V3 fee tiers (in hundredths of a bip)
FEE_TIERS: list[int] = [100, 500, 3000, 10000]

# Tick spacing per fee tier
TICK_SPACINGS: dict[int, int] = {100: 1, 500: 10, 3000: 60, 10000: 200}

# Full-range tick bounds
MIN_TICK: int = -887272
MAX_TICK: int = 887272

# Network ID to chain ID mapping (subset relevant to Uniswap)
NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "ethereum-mainnet": 1,
    "arbitrum-mainnet": 42161,
    "optimism-mainnet": 10,
    "polygon-mainnet": 137,
    "base-mainnet": 8453,
}

# Native token symbol per chain ID
NATIVE_WRAPPED_SYMBOL: dict[int, str] = {
    1: "WETH",
    42161: "WETH",
    10: "WETH",
    137: "WMATIC",
    8453: "WETH",
}

# QuoterV2 ABI - quoteExactInputSingle
QUOTER_V2_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "fee", "type": "uint24"},
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

# SwapRouter02 ABI - exactInputSingle
SWAP_ROUTER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "recipient", "type": "address"},
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

# NonfungiblePositionManager ABI (minimal)
POSITION_MANAGER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "token0", "type": "address"},
                    {"name": "token1", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "tickLower", "type": "int24"},
                    {"name": "tickUpper", "type": "int24"},
                    {"name": "amount0Desired", "type": "uint256"},
                    {"name": "amount1Desired", "type": "uint256"},
                    {"name": "amount0Min", "type": "uint256"},
                    {"name": "amount1Min", "type": "uint256"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
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
            {"name": "fee", "type": "uint24"},
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
]

# UniswapV3Factory ABI (minimal)
FACTORY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]
