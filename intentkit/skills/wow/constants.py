"""Constants for WOW skill (Zora Wow ERC20 memecoin protocol)."""

# WOW Factory contract addresses by network
WOW_FACTORY_CONTRACT_ADDRESSES = {
    "base-sepolia": "0x04870e22fa217Cb16aa00501D7D5253B8838C1eA",
    "base-mainnet": "0x997020E5F59cCB79C74D527Be492Cc610CB9fA2B",
}

# Network-specific addresses
ADDRESSES = {
    "base-sepolia": {
        "wow_factory": "0xB09c0b1b18369Ef62e896D5a49Af8d65EFa0A404",
        "wow_factory_impl": "0xB522291f22FE7FA45D56797F7A685D5c637Edc32",
        "wow": "0x15ba66e376856F3F6FE53dE9eeAb10dEF10E8C92",
        "bonding_curve": "0xCE00c75B9807A2aA87B2297cA7Dc1C0190137D6F",
        "nonfungible_position_manager": "0x27F971cb582BF9E50F397e4d29a5C7A34f11faA2",
        "swap_router_02": "0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4",
        "weth": "0x4200000000000000000000000000000000000006",
        "uniswap_quoter": "0xC5290058841028F1614F3A6F0F5816cAd0df5E27",
    },
    "base-mainnet": {
        "wow_factory": "0xA06262157905913f855573f53AD48DE2D4ba1F4A",
        "wow_factory_impl": "0xe4c17055048aEe01D0d122804816fEe5E6ac4A67",
        "wow": "0x293997C6a1f2A1cA3aB971f548c4D95585E46282",
        "bonding_curve": "0x264ece5D58A576cc775B719bf182F2946076bE78",
        "nonfungible_position_manager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
        "swap_router_02": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "weth": "0x4200000000000000000000000000000000000006",
        "uniswap_quoter": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
    },
}

# Generic token metadata URI for tokens created without custom metadata
GENERIC_TOKEN_METADATA_URI = "ipfs://QmY1GqprFYvojCcUEKgqHeDj9uhZD9jmYGrQTfA9vAE78J"

# Supported chain IDs
SUPPORTED_CHAIN_IDS = ["8453", "84532"]

# WOW Factory ABI (for creating tokens)
WOW_FACTORY_ABI = [
    {
        "type": "constructor",
        "inputs": [
            {
                "name": "_tokenImplementation",
                "type": "address",
                "internalType": "address",
            },
            {"name": "_bondingCurve", "type": "address", "internalType": "address"},
        ],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "deploy",
        "inputs": [
            {"name": "_tokenCreator", "type": "address", "internalType": "address"},
            {"name": "_platformReferrer", "type": "address", "internalType": "address"},
            {"name": "_tokenURI", "type": "string", "internalType": "string"},
            {"name": "_name", "type": "string", "internalType": "string"},
            {"name": "_symbol", "type": "string", "internalType": "string"},
        ],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "bondingCurve",
        "inputs": [],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "implementation",
        "inputs": [],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "owner",
        "inputs": [],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "tokenImplementation",
        "inputs": [],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "view",
    },
]

# WOW Token ABI (for buy/sell operations)
WOW_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "address", "name": "refundRecipient", "type": "address"},
            {"internalType": "address", "name": "orderReferrer", "type": "address"},
            {"internalType": "string", "name": "comment", "type": "string"},
            {
                "internalType": "enum IWow.MarketType",
                "name": "expectedMarketType",
                "type": "uint8",
            },
            {"internalType": "uint256", "name": "minOrderSize", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
        "name": "buy",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokensToSell", "type": "uint256"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "address", "name": "orderReferrer", "type": "address"},
            {"internalType": "string", "name": "comment", "type": "string"},
            {
                "internalType": "enum IWow.MarketType",
                "name": "expectedMarketType",
                "type": "uint8",
            },
            {"internalType": "uint256", "name": "minPayoutSize", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
        "name": "sell",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "ethOrderSize", "type": "uint256"}
        ],
        "name": "getEthBuyQuote",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenOrderSize", "type": "uint256"}
        ],
        "name": "getTokenSellQuote",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "marketType",
        "outputs": [
            {"internalType": "enum IWow.MarketType", "name": "", "type": "uint8"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "poolAddress",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
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
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "tokenCreator",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Uniswap V3 Quoter ABI (for graduated tokens)
UNISWAP_QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {
                        "internalType": "uint160",
                        "name": "sqrtPriceLimitX96",
                        "type": "uint160",
                    },
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {
                "internalType": "uint32",
                "name": "initializedTicksCrossed",
                "type": "uint32",
            },
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Uniswap V3 Pool ABI (for pool info)
UNISWAP_V3_ABI = [
    {
        "inputs": [],
        "name": "fee",
        "outputs": [{"internalType": "uint24", "name": "", "type": "uint24"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {
                "internalType": "uint16",
                "name": "observationCardinality",
                "type": "uint16",
            },
            {
                "internalType": "uint16",
                "name": "observationCardinalityNext",
                "type": "uint16",
            },
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]
