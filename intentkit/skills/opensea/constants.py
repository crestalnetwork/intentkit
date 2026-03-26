"""OpenSea / Seaport protocol constants."""

# OpenSea API base URL
OPENSEA_API_BASE_URL = "https://api.opensea.io/api/v2"

# Network ID to OpenSea chain name mapping
NETWORK_TO_CHAIN: dict[str, str] = {
    "ethereum-mainnet": "ethereum",
    "polygon-mainnet": "matic",
    "arbitrum-mainnet": "arbitrum",
    "optimism-mainnet": "optimism",
    "base-mainnet": "base",
    "avalanche-mainnet": "avalanche",
    "bnb-mainnet": "bsc",
    "sepolia-testnet": "sepolia",
}

# Seaport 1.6 contract address (same across all chains)
SEAPORT_ADDRESS = "0x00000000000000ADc04C56Bf30aC9d3c0aAF14dC"

# OpenSea marketplace protocol address (used as protocol_address in API calls)
# This is different from the Seaport verifying contract
OPENSEA_PROTOCOL_ADDRESS = "0x0000000000000068F116a894984e2DB1123eB395"

# OpenSea conduit key for Seaport
OPENSEA_CONDUIT_KEY = (
    "0x0000007b02230091a7ed01230072f7006a004d60a8d4e71d599b8104250f0000"
)

# OpenSea conduit address (derived from conduit key)
OPENSEA_CONDUIT_ADDRESS = "0x1E0049783F008A0085193E00003D00cd54003c71"

# SignedZone address for OpenSea orders
OPENSEA_ZONE_ADDRESS = "0x000056F7000000EcE9003ca63978907a00FFD100"

# Seaport order types
ORDER_TYPE_FULL_RESTRICTED = 2  # Standard OpenSea listing with zone

# Seaport item types
ITEM_TYPE_NATIVE = 0  # ETH
ITEM_TYPE_ERC20 = 1
ITEM_TYPE_ERC721 = 2
ITEM_TYPE_ERC1155 = 3

# OpenSea fee basis points (2.5%)
OPENSEA_FEE_BPS = 250
OPENSEA_FEE_RECIPIENT = "0x0000a26b00c1F0DF003000390027140000fAa719"

# Zero address and zero bytes32
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ZERO_BYTES32 = "0x0000000000000000000000000000000000000000000000000000000000000000"

# EIP-712 domain for Seaport 1.6
SEAPORT_EIP712_DOMAIN = {
    "name": "Seaport",
    "version": "1.6",
    # chainId and verifyingContract are set dynamically
}

# EIP-712 types for Seaport OrderComponents
SEAPORT_ORDER_TYPES = {
    "OrderComponents": [
        {"name": "offerer", "type": "address"},
        {"name": "zone", "type": "address"},
        {"name": "offer", "type": "OfferItem[]"},
        {"name": "consideration", "type": "ConsiderationItem[]"},
        {"name": "orderType", "type": "uint8"},
        {"name": "startTime", "type": "uint256"},
        {"name": "endTime", "type": "uint256"},
        {"name": "zoneHash", "type": "bytes32"},
        {"name": "salt", "type": "uint256"},
        {"name": "conduitKey", "type": "bytes32"},
        {"name": "counter", "type": "uint256"},
    ],
    "OfferItem": [
        {"name": "itemType", "type": "uint8"},
        {"name": "token", "type": "address"},
        {"name": "identifierOrCriteria", "type": "uint256"},
        {"name": "startAmount", "type": "uint256"},
        {"name": "endAmount", "type": "uint256"},
    ],
    "ConsiderationItem": [
        {"name": "itemType", "type": "uint8"},
        {"name": "token", "type": "address"},
        {"name": "identifierOrCriteria", "type": "uint256"},
        {"name": "startAmount", "type": "uint256"},
        {"name": "endAmount", "type": "uint256"},
        {"name": "recipient", "type": "address"},
    ],
}

# Seaport ABI (only functions we need)
SEAPORT_ABI = [
    {
        "name": "getCounter",
        "type": "function",
        "inputs": [{"name": "offerer", "type": "address"}],
        "outputs": [{"name": "counter", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "fulfillOrder",
        "type": "function",
        "inputs": [
            {
                "name": "order",
                "type": "tuple",
                "components": [
                    {
                        "name": "parameters",
                        "type": "tuple",
                        "components": [
                            {"name": "offerer", "type": "address"},
                            {"name": "zone", "type": "address"},
                            {
                                "name": "offer",
                                "type": "tuple[]",
                                "components": [
                                    {"name": "itemType", "type": "uint8"},
                                    {"name": "token", "type": "address"},
                                    {
                                        "name": "identifierOrCriteria",
                                        "type": "uint256",
                                    },
                                    {"name": "startAmount", "type": "uint256"},
                                    {"name": "endAmount", "type": "uint256"},
                                ],
                            },
                            {
                                "name": "consideration",
                                "type": "tuple[]",
                                "components": [
                                    {"name": "itemType", "type": "uint8"},
                                    {"name": "token", "type": "address"},
                                    {
                                        "name": "identifierOrCriteria",
                                        "type": "uint256",
                                    },
                                    {"name": "startAmount", "type": "uint256"},
                                    {"name": "endAmount", "type": "uint256"},
                                    {"name": "recipient", "type": "address"},
                                ],
                            },
                            {"name": "orderType", "type": "uint8"},
                            {"name": "startTime", "type": "uint256"},
                            {"name": "endTime", "type": "uint256"},
                            {"name": "zoneHash", "type": "bytes32"},
                            {"name": "salt", "type": "uint256"},
                            {"name": "conduitKey", "type": "bytes32"},
                            {
                                "name": "totalOriginalConsiderationItems",
                                "type": "uint256",
                            },
                        ],
                    },
                    {"name": "signature", "type": "bytes"},
                ],
            },
            {"name": "fulfillerConduitKey", "type": "bytes32"},
        ],
        "outputs": [{"name": "fulfilled", "type": "bool"}],
        "stateMutability": "payable",
    },
]

# ERC721 ABI (only approval functions we need)
ERC721_APPROVAL_ABI = [
    {
        "name": "isApprovedForAll",
        "type": "function",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "operator", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
    },
    {
        "name": "setApprovalForAll",
        "type": "function",
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
]
