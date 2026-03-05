"""PancakeSwap V3 contract addresses and ABIs."""

from typing import Any

# PancakeSwap V3 QuoterV2 addresses per chain ID
QUOTER_V2_ADDRESSES: dict[int, str] = {
    56: "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",  # BSC
    1: "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",  # Ethereum
    8453: "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",  # Base
    42161: "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",  # Arbitrum
    59144: "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",  # Linea
}

# PancakeSwap V3 SmartRouter addresses per chain ID
SMART_ROUTER_ADDRESSES: dict[int, str] = {
    56: "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",  # BSC
    1: "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",  # Ethereum
    8453: "0x678Aa4bF4E210cf2166753e054d5b7c31cc7fa86",  # Base
    42161: "0x32226588378236Fd0c7c4053999F88aC0e5cAc77",  # Arbitrum
    59144: "0x678Aa4bF4E210cf2166753e054d5b7c31cc7fa86",  # Linea
}

# Wrapped native token addresses per chain ID
WRAPPED_NATIVE_ADDRESSES: dict[int, str] = {
    56: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
    1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    8453: "0x4200000000000000000000000000000000000006",  # WETH
    42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH
    59144: "0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f",  # WETH
}

# PancakeSwap V3 NonfungiblePositionManager (same on all chains)
POSITION_MANAGER_ADDRESS: str = "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364"

# PancakeSwap V3 Factory (same on all chains)
FACTORY_ADDRESS: str = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

# MasterChef V3 addresses per chain ID
MASTERCHEF_V3_ADDRESSES: dict[int, str] = {
    56: "0x556B9306565093C855AEA9AE92A594704c2Cd59e",  # BSC
    1: "0x556B9306565093C855AEA9AE92A594704c2Cd59e",  # Ethereum
    42161: "0x5e09ACf80C0296740eC5d6F643005a4ef8DaA694",  # Arbitrum
    8453: "0xC6A2Db661D5a5690172d8eB0a7DEA2d3008665A3",  # Base
    59144: "0x22E2f236065B780FA33EC8C4E58b99ebc8B55c57",  # Linea
}

# Common V3 fee tiers (in hundredths of a bip)
FEE_TIERS: list[int] = [100, 500, 2500, 10000]

# Tick spacing per fee tier
TICK_SPACINGS: dict[int, int] = {100: 1, 500: 10, 2500: 50, 10000: 200}

# Full-range tick bounds
MIN_TICK: int = -887272
MAX_TICK: int = 887272

# Network ID to chain ID mapping (subset relevant to PancakeSwap)
NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "bnb-mainnet": 56,
    "ethereum-mainnet": 1,
    "base-mainnet": 8453,
    "arbitrum-mainnet": 42161,
    "linea-mainnet": 59144,
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

# SmartRouter ABI - exactInputSingle
SMART_ROUTER_ABI: list[dict[str, Any]] = [
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
        "inputs": [{"name": "account", "type": "address"}],
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
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# PancakeV3Factory ABI (minimal)
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

# MasterChef V3 ABI (minimal)
MASTERCHEF_V3_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "_tokenId", "type": "uint256"},
            {"name": "_to", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "reward", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "pendingCake",
        "outputs": [{"name": "reward", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "userPositionInfos",
        "outputs": [
            {"name": "liquidity", "type": "uint128"},
            {"name": "boostLiquidity", "type": "uint128"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "rewardGrowthInside", "type": "uint256"},
            {"name": "reward", "type": "uint256"},
            {"name": "user", "type": "address"},
            {"name": "pid", "type": "uint256"},
            {"name": "boostMultiplier", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]
