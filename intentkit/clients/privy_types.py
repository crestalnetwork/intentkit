from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

# =============================================================================
# Chain Configuration
# =============================================================================


# Safe Singleton addresses (L2 version for most chains)
# Canonical deployment: 0x3E5c63644E683549055b9Be8653de26E0B4CD36E
# EIP-155 deployment: 0xfb1bffC9d739B8D520DaF37dF666da4C687191EA
# Both are functionally identical Safe L2 contracts, just deployed differently
SAFE_SINGLETON_L2_CANONICAL = "0x3E5c63644E683549055b9Be8653de26E0B4CD36E"
SAFE_SINGLETON_L2_EIP155 = "0xfb1bffC9d739B8D520DaF37dF666da4C687191EA"


@dataclass
class ChainConfig:
    """Configuration for a blockchain network."""

    chain_id: int
    name: str
    safe_tx_service_url: str
    rpc_url: str | None = None
    usdc_address: str | None = None
    allowance_module_address: str = "0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134"
    # Safe singleton address - use L2 version for L2 chains
    safe_singleton_address: str = SAFE_SINGLETON_L2_EIP155


# Chain configurations mapping IntentKit network_id to Safe chain config
CHAIN_CONFIGS: dict[str, ChainConfig] = {
    # Mainnets
    "bnb-mainnet": ChainConfig(
        chain_id=56,
        name="BNB Smart Chain",
        safe_tx_service_url="https://safe-transaction-bsc.safe.global",
        usdc_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        safe_singleton_address=SAFE_SINGLETON_L2_CANONICAL,
    ),
    "base-mainnet": ChainConfig(
        chain_id=8453,
        name="Base",
        safe_tx_service_url="https://safe-transaction-base.safe.global",
        usdc_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    ),
    "ethereum-mainnet": ChainConfig(
        chain_id=1,
        name="Ethereum",
        safe_tx_service_url="https://safe-transaction-mainnet.safe.global",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    ),
    "polygon-mainnet": ChainConfig(
        chain_id=137,
        name="Polygon",
        safe_tx_service_url="https://safe-transaction-polygon.safe.global",
        usdc_address="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        # Note: Polygon uses different allowance module address
        allowance_module_address="0x1Fb403834C911eB98d56E74F5182b0d64C3b3b4D",
    ),
    "arbitrum-mainnet": ChainConfig(
        chain_id=42161,
        name="Arbitrum One",
        safe_tx_service_url="https://safe-transaction-arbitrum.safe.global",
        usdc_address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    ),
    "optimism-mainnet": ChainConfig(
        chain_id=10,
        name="Optimism",
        safe_tx_service_url="https://safe-transaction-optimism.safe.global",
        usdc_address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
    ),
    # Testnets
    "base-sepolia": ChainConfig(
        chain_id=84532,
        name="Base Sepolia",
        safe_tx_service_url="https://safe-transaction-base-sepolia.safe.global",
        usdc_address="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        # Deployed custom Allowance Module v1.3.0 since canonical is missing
        allowance_module_address="0x3cfE2CEb10FC1654B5F4422704288D08BDF7d27F",
    ),
    "sepolia": ChainConfig(
        chain_id=11155111,
        name="Sepolia",
        safe_tx_service_url="https://safe-transaction-sepolia.safe.global",
        usdc_address="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
    ),
}

# Safe contract addresses (same across most EVM chains for v1.3.0)
SAFE_PROXY_FACTORY_ADDRESS = "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
SAFE_FALLBACK_HANDLER_ADDRESS = "0xf48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4"
MULTI_SEND_ADDRESS = "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761"
MULTI_SEND_CALL_ONLY_ADDRESS = "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D"


# =============================================================================
# ABI Definitions
# =============================================================================

# Safe ABI (minimal for our needs)
SAFE_ABI = [
    {
        "inputs": [
            {"name": "_owners", "type": "address[]"},
            {"name": "_threshold", "type": "uint256"},
            {"name": "to", "type": "address"},
            {"name": "data", "type": "bytes"},
            {"name": "fallbackHandler", "type": "address"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint256"},
            {"name": "paymentReceiver", "type": "address"},
        ],
        "name": "setup",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [{"name": "module", "type": "address"}],
        "name": "enableModule",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [{"name": "module", "type": "address"}],
        "name": "isModuleEnabled",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getOwners",
        "outputs": [{"name": "", "type": "address[]"}],
        "type": "function",
    },
]

# Allowance Module ABI
ALLOWANCE_MODULE_ABI = [
    {
        "inputs": [{"name": "delegate", "type": "address"}],
        "name": "addDelegate",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "delegate", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "allowanceAmount", "type": "uint96"},
            {"name": "resetTimeMin", "type": "uint16"},
            {"name": "resetBaseMin", "type": "uint32"},
        ],
        "name": "setAllowance",
        "outputs": [],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "delegate", "type": "address"},
            {"name": "token", "type": "address"},
        ],
        "name": "getTokenAllowance",
        "outputs": [{"name": "", "type": "uint256[5]"}],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint96"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint96"},
            {"name": "nonce", "type": "uint16"},
        ],
        "name": "generateTransferHash",
        "outputs": [{"name": "", "type": "bytes32"}],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "safe", "type": "address"},
            {"name": "token", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint96"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint96"},
            {"name": "delegate", "type": "address"},
            {"name": "signature", "type": "bytes"},
        ],
        "name": "executeAllowanceTransfer",
        "outputs": [],
        "type": "function",
    },
]

# ERC20 ABI (minimal)
ERC20_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


# SafeProxyFactory ABI
SAFE_PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "_singleton", "type": "address"},
            {"name": "initializer", "type": "bytes"},
            {"name": "saltNonce", "type": "uint256"},
        ],
        "name": "createProxyWithNonce",
        "outputs": [{"name": "proxy", "type": "address"}],
        "type": "function",
    },
]


# =============================================================================
# Data Models
# =============================================================================


class PrivyWallet(BaseModel):
    """Privy server wallet response model."""

    id: str
    address: str
    chain_type: str


@dataclass
class TransactionRequest:
    """A transaction request for the wallet provider."""

    to: str
    value: int = 0
    data: bytes = b""


@dataclass
class TransactionResult:
    """Result of a transaction execution."""

    success: bool
    tx_hash: str | None = None
    error: str | None = None


# =============================================================================
# Abstract Wallet Provider Interface
# =============================================================================


class WalletProvider(ABC):
    """
    Abstract base class for wallet providers.

    This interface allows different wallet implementations (Safe, CDP, etc.)
    to be used interchangeably by agents.
    """

    @abstractmethod
    async def get_address(self) -> str:
        """Get the wallet's public address."""
        pass

    @abstractmethod
    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a transaction.

        Args:
            to: Destination address
            value: Amount of native token to send (in wei)
            data: Transaction calldata
            chain_id: Optional chain ID (uses default if not specified)

        Returns:
            TransactionResult with success status and tx hash
        """
        pass

    @abstractmethod
    async def transfer_erc20(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Transfer ERC20 tokens.

        Args:
            token_address: The token contract address
            to: Recipient address
            amount: Amount to transfer (in token's smallest unit)
            chain_id: Optional chain ID

        Returns:
            TransactionResult with success status and tx hash
        """
        pass

    @abstractmethod
    async def get_balance(self, chain_id: int | None = None) -> int:
        """Get native token balance in wei."""
        pass

    @abstractmethod
    async def get_erc20_balance(
        self,
        token_address: str,
        chain_id: int | None = None,
    ) -> int:
        """Get ERC20 token balance."""
        pass
