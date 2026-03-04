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

# Common V3 fee tiers (in hundredths of a bip)
FEE_TIERS: list[int] = [500, 2500, 10000]

# Network ID to chain ID mapping (subset relevant to PancakeSwap)
NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "bnb-mainnet": 56,
    "ethereum-mainnet": 1,
    "base-mainnet": 8453,
    "arbitrum-mainnet": 42161,
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
