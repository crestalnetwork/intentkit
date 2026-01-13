"""
Privy + Safe Smart Wallet Client

This module provides integration between Privy server wallets (EOA signers)
and Safe smart accounts for autonomous agent transactions.

Architecture:
- Privy provides the EOA (Externally Owned Account) as the signer/owner
- Safe provides the smart account with spending limits via Allowance Module
- The agent's public address is the Safe smart account address
- Transactions are signed by Privy and executed through Safe
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from eth_abi import encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address
from pydantic import BaseModel
from web3 import AsyncWeb3

from intentkit.config.config import config
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


# =============================================================================
# Chain Configuration
# =============================================================================


@dataclass
class ChainConfig:
    """Configuration for a blockchain network."""

    chain_id: int
    name: str
    safe_tx_service_url: str
    rpc_url: str | None = None
    usdc_address: str | None = None
    allowance_module_address: str = "0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134"


# Chain configurations mapping IntentKit network_id to Safe chain config
CHAIN_CONFIGS: dict[str, ChainConfig] = {
    # Mainnets
    "bnb-mainnet": ChainConfig(
        chain_id=56,
        name="BNB Smart Chain",
        safe_tx_service_url="https://safe-transaction-bsc.safe.global",
        usdc_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
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
SAFE_SINGLETON_ADDRESS = "0xd9Db270c1B5E3Bd161E8c8503c55cEABe709501d"
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


# =============================================================================
# Privy Client
# =============================================================================


class PrivyClient:
    """Client for interacting with Privy Server Wallet API."""

    def __init__(self) -> None:
        self.app_id: str | None = config.privy_app_id
        self.app_secret: str | None = config.privy_app_secret
        self.base_url: str = "https://auth.privy.io/api/v1"

        if not self.app_id or not self.app_secret:
            logger.warning("Privy credentials not configured")

    def _get_headers(self) -> dict[str, str]:
        return {
            "privy-app-id": self.app_id or "",
            "Content-Type": "application/json",
        }

    async def create_wallet(self, owner_id: str | None = None) -> PrivyWallet:
        """Create a new server wallet.

        Args:
            owner_id: Optional Privy user ID to set as the wallet owner.
                     When provided, the wallet will be owned by this user.

        Note: Privy's create wallet API does not support idempotency keys.
        Idempotency keys are only supported for transaction APIs via the
        'privy-idempotency-key' HTTP header.
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets"
        payload: dict[str, Any] = {
            "chain_type": "ethereum",
        }
        if owner_id:
            payload["owner"] = {"user_id": owner_id}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Privy create wallet failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to create Privy wallet",
                )

            data = response.json()
            return PrivyWallet(
                id=data["id"],
                address=data["address"],
                chain_type=data["chain_type"],
            )

    async def sign_message(self, wallet_id: str, message: str) -> str:
        """Sign a message using the Privy server wallet.

        Uses personal_sign which signs the message with Ethereum's
        personal_sign prefix: "\\x19Ethereum Signed Message:\\n" + len(message) + message
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "personal_sign",
            "params": {
                "message": message,
                "encoding": "utf-8",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Privy sign message failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign message with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def sign_hash(self, wallet_id: str, hash_bytes: bytes) -> str:
        """Sign a raw hash directly using the Privy server wallet.

        Uses secp256k1_sign which signs the raw hash without any prefix.
        This is different from personal_sign which adds Ethereum's message prefix.
        """
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        # Privy expects the hash as a hex string with 0x prefix
        hash_hex = "0x" + hash_bytes.hex()

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "secp256k1_sign",
            "params": {
                "hash": hash_hex,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Privy sign hash failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign hash with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def sign_typed_data(self, wallet_id: str, typed_data: dict[str, Any]) -> str:
        """Sign typed data (EIP-712) using the Privy server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "eth_signTypedData_v4",
            "params": {
                "typed_data": typed_data,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Privy sign typed data failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    "Failed to sign typed data with Privy wallet",
                )

            data = response.json()
            return data["data"]["signature"]

    async def send_transaction(
        self,
        wallet_id: str,
        chain_id: int,
        to: str,
        value: int = 0,
        data: str = "0x",
    ) -> str:
        """Send a transaction using the Privy server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "eth_sendTransaction",
            "caip2": f"eip155:{chain_id}",
            "params": {
                "transaction": {
                    "to": to,
                    "value": hex(value),
                    "data": data,
                }
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.app_id, self.app_secret),
                headers=self._get_headers(),
                timeout=60.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Privy send transaction failed: {response.text}")
                raise IntentKitAPIError(
                    response.status_code,
                    "PrivyAPIError",
                    f"Failed to send transaction: {response.text}",
                )

            data_response = response.json()
            return data_response["data"]["hash"]


# =============================================================================
# Safe Smart Account Client
# =============================================================================


class SafeClient:
    """Client for interacting with Safe smart accounts."""

    def __init__(
        self,
        network_id: str = "base-mainnet",
        rpc_url: str | None = None,
    ) -> None:
        self.network_id = network_id
        self.chain_config = CHAIN_CONFIGS.get(network_id)
        if not self.chain_config:
            raise ValueError(f"Unsupported network: {network_id}")

        self.rpc_url = rpc_url or self.chain_config.rpc_url
        self.api_key: str | None = config.safe_api_key

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_chain_id(self) -> int:
        """Get the chain ID for the current network."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        return self.chain_config.chain_id

    def predict_safe_address(
        self,
        owner_address: str,
        salt_nonce: int = 0,
        threshold: int = 1,
    ) -> str:
        """
        Predict the counterfactual Safe address for a given owner.

        This calculates the CREATE2 address that would be deployed
        for a Safe with the given parameters.
        """
        owner_address = to_checksum_address(owner_address)

        # Build the initializer (setup call data)
        initializer = self._build_safe_initializer(
            owners=[owner_address],
            threshold=threshold,
        )

        # Calculate CREATE2 address
        return self._calculate_create2_address(initializer, salt_nonce)

    def _build_safe_initializer(
        self,
        owners: list[str],
        threshold: int,
        fallback_handler: str = SAFE_FALLBACK_HANDLER_ADDRESS,
    ) -> bytes:
        """Build the Safe setup initializer data."""
        # setup(address[] _owners, uint256 _threshold, address to, bytes data,
        #       address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)
        setup_data = encode(
            [
                "address[]",
                "uint256",
                "address",
                "bytes",
                "address",
                "address",
                "uint256",
                "address",
            ],
            [
                owners,
                threshold,
                "0x0000000000000000000000000000000000000000",  # to
                b"",  # data
                fallback_handler,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                "0x0000000000000000000000000000000000000000",  # paymentReceiver
            ],
        )

        # Function selector for setup()
        setup_selector = keccak(
            text="setup(address[],uint256,address,bytes,address,address,uint256,address)"
        )[:4]

        return setup_selector + setup_data

    def _calculate_create2_address(self, initializer: bytes, salt_nonce: int) -> str:
        """Calculate the CREATE2 address for a Safe deployment.

        The SafeProxyFactory calculates CREATE2 address as follows:
        - salt = keccak256(abi.encodePacked(keccak256(initializer), saltNonce))
        - deploymentData = abi.encodePacked(type(SafeProxy).creationCode, uint256(uint160(_singleton)))
        - address = keccak256(0xff ++ factory ++ salt ++ keccak256(deploymentData))[12:]

        Note: The initializer is NOT included in the deploymentData/init_code_hash,
        it's only used in the salt calculation.
        """
        # Salt = keccak256(keccak256(initializer) ++ saltNonce)
        initializer_hash = keccak(initializer)
        salt = keccak(initializer_hash + encode(["uint256"], [salt_nonce]))

        # Proxy creation code (Safe v1.3.0 GnosisSafeProxyFactory)
        # This is the bytecode that deploys a minimal proxy pointing to the singleton
        proxy_creation_code = bytes.fromhex(
            "608060405234801561001057600080fd5b506040516101e63803806101e68339818101604052602081101561003357600080fd5b8101908080519060200190929190505050600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614156100ca576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806101c46022913960400191505060405180910390fd5b806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055505060ab806101196000396000f3fe608060405273ffffffffffffffffffffffffffffffffffffffff600054167fa619486e0000000000000000000000000000000000000000000000000000000060003514156050578060005260206000f35b3660008037600080366000845af43d6000803e60008114156070573d6000fd5b3d6000f3fea2646970667358221220d1429297349653a4918076d650332de1a1068c5f3e07c5c82360c277770b955264736f6c63430007060033496e76616c69642073696e676c65746f6e20616464726573732070726f7669646564"
        )

        # deploymentData = creationCode + abi.encode(singleton)
        # Note: We do NOT include the initializer here - that's only for the salt
        init_code = proxy_creation_code + encode(["address"], [SAFE_SINGLETON_ADDRESS])
        init_code_hash = keccak(init_code)

        # CREATE2 address calculation: keccak256(0xff ++ factory ++ salt ++ init_code_hash)[12:]
        factory_address = bytes.fromhex(SAFE_PROXY_FACTORY_ADDRESS[2:])
        create2_input = b"\xff" + factory_address + salt + init_code_hash
        address_bytes = keccak(create2_input)[12:]

        return to_checksum_address(address_bytes)

    async def is_deployed(self, address: str, rpc_url: str) -> bool:
        """Check if a contract is deployed at the given address."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getCode",
                    "params": [address, "latest"],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                return False

            result = response.json().get("result", "0x")
            return len(result) > 2

    async def get_safe_info(self, safe_address: str) -> dict[str, Any] | None:
        """Get Safe information from the Transaction Service."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        url = f"{self.chain_config.safe_tx_service_url}/api/v1/safes/{safe_address}/"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), timeout=30.0)

            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                logger.error(f"Safe get info failed: {response.text}")
                return None

            return response.json()

    async def get_nonce(self, safe_address: str, rpc_url: str) -> int:
        """Get the current nonce for a Safe."""
        # Encode the nonce() call
        nonce_selector = keccak(text="nonce()")[:4]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": safe_address, "data": "0x" + nonce_selector.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get Safe nonce")

            result = response.json().get("result", "0x0")
            return int(result, 16)


# =============================================================================
# Safe Wallet Provider (implements WalletProvider interface)
# =============================================================================


class SafeWalletProvider(WalletProvider):
    """
    Safe smart account wallet provider.

    This provider uses a Privy EOA as the owner/signer and a Safe smart
    account as the public address with spending limit support.
    """

    def __init__(
        self,
        privy_wallet_id: str,
        privy_wallet_address: str,
        safe_address: str,
        network_id: str = "base-mainnet",
        rpc_url: str | None = None,
    ) -> None:
        self.privy_wallet_id = privy_wallet_id
        self.privy_wallet_address = to_checksum_address(privy_wallet_address)
        self.safe_address = to_checksum_address(safe_address)
        self.network_id = network_id

        self.chain_config = CHAIN_CONFIGS.get(network_id)
        if not self.chain_config:
            raise ValueError(f"Unsupported network: {network_id}")

        self.rpc_url = rpc_url
        self.privy_client = PrivyClient()
        self.safe_client = SafeClient(network_id, rpc_url)

    async def get_address(self) -> str:
        """Get the Safe smart account address."""
        return self.safe_address

    async def execute_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a transaction through the Safe.

        For now, this uses the Privy EOA to directly execute transactions
        on behalf of the Safe (as owner). In the future, this could use
        the Safe Transaction Service for better UX.
        """
        try:
            # Get the RPC URL for the chain
            if self.chain_config is None:
                return TransactionResult(
                    success=False,
                    error="Chain config not initialized",
                )
            target_chain_id = chain_id or self.chain_config.chain_id
            rpc_url = self._get_rpc_url_for_chain(target_chain_id)

            if not rpc_url:
                return TransactionResult(
                    success=False,
                    error=f"No RPC URL configured for chain {target_chain_id}",
                )

            # Build Safe transaction
            safe_tx_data = self._encode_safe_exec_transaction(to, value, data)

            # Send via Privy
            tx_hash = await self.privy_client.send_transaction(
                wallet_id=self.privy_wallet_id,
                chain_id=target_chain_id,
                to=self.safe_address,
                value=0,
                data="0x" + safe_tx_data.hex(),
            )

            return TransactionResult(success=True, tx_hash=tx_hash)

        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def transfer_erc20(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """Transfer ERC20 tokens from the Safe."""
        # Encode ERC20 transfer call
        transfer_selector = keccak(text="transfer(address,uint256)")[:4]
        transfer_data = transfer_selector + encode(
            ["address", "uint256"],
            [to_checksum_address(to), amount],
        )

        return await self.execute_transaction(
            to=to_checksum_address(token_address),
            value=0,
            data=transfer_data,
            chain_id=chain_id,
        )

    async def execute_allowance_transfer(
        self,
        token_address: str,
        to: str,
        amount: int,
        chain_id: int | None = None,
    ) -> TransactionResult:
        """
        Execute a token transfer using the Allowance Module.

        This allows the agent (as delegate) to spend tokens within
        the configured spending limit without requiring owner signatures.
        """
        try:
            if self.chain_config is None:
                return TransactionResult(
                    success=False,
                    error="Chain config not initialized",
                )
            target_chain_id = chain_id or self.chain_config.chain_id
            rpc_url = self._get_rpc_url_for_chain(target_chain_id)

            if not rpc_url:
                return TransactionResult(
                    success=False,
                    error=f"No RPC URL configured for chain {target_chain_id}",
                )

            # Get allowance module address for this chain
            chain_config = self._get_chain_config_for_id(target_chain_id)
            if not chain_config:
                return TransactionResult(
                    success=False,
                    error=f"Chain {target_chain_id} not configured",
                )

            allowance_module = chain_config.allowance_module_address

            # Get current allowance nonce
            nonce = await self._get_allowance_nonce(
                rpc_url, allowance_module, token_address
            )

            # Generate transfer hash
            transfer_hash = await self._generate_transfer_hash(
                rpc_url=rpc_url,
                allowance_module=allowance_module,
                token_address=token_address,
                to=to,
                amount=amount,
                nonce=nonce,
            )

            # Sign the hash with Privy
            signature = await self.privy_client.sign_hash(
                self.privy_wallet_id, transfer_hash
            )

            # Execute the allowance transfer
            exec_data = self._encode_execute_allowance_transfer(
                token_address=token_address,
                to=to,
                amount=amount,
                signature=signature,
            )

            # Send the transaction (anyone can submit this with valid signature)
            tx_hash = await self.privy_client.send_transaction(
                wallet_id=self.privy_wallet_id,
                chain_id=target_chain_id,
                to=allowance_module,
                value=0,
                data="0x" + exec_data.hex(),
            )

            return TransactionResult(success=True, tx_hash=tx_hash)

        except Exception as e:
            logger.error(f"Allowance transfer failed: {e}")
            return TransactionResult(success=False, error=str(e))

    async def get_balance(self, chain_id: int | None = None) -> int:
        """Get native token balance of the Safe."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        target_chain_id = chain_id or self.chain_config.chain_id
        rpc_url = self._get_rpc_url_for_chain(target_chain_id)

        if not rpc_url:
            raise IntentKitAPIError(
                500, "ConfigError", f"No RPC URL for chain {target_chain_id}"
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [self.safe_address, "latest"],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get balance")

            result = response.json().get("result", "0x0")
            return int(result, 16)

    async def get_erc20_balance(
        self,
        token_address: str,
        chain_id: int | None = None,
    ) -> int:
        """Get ERC20 token balance of the Safe."""
        if self.chain_config is None:
            raise ValueError("Chain config not initialized")
        target_chain_id = chain_id or self.chain_config.chain_id
        rpc_url = self._get_rpc_url_for_chain(target_chain_id)

        if not rpc_url:
            raise IntentKitAPIError(
                500, "ConfigError", f"No RPC URL for chain {target_chain_id}"
            )

        # Encode balanceOf call
        balance_selector = keccak(text="balanceOf(address)")[:4]
        call_data = balance_selector + encode(["address"], [self.safe_address])

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {
                            "to": to_checksum_address(token_address),
                            "data": "0x" + call_data.hex(),
                        },
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get token balance")

            result = response.json().get("result", "0x0")
            return int(result, 16)

    def _get_rpc_url_for_chain(self, chain_id: int) -> str | None:
        """Get RPC URL for a specific chain ID."""
        if self.chain_config is None:
            return None
        if self.rpc_url and self.chain_config.chain_id == chain_id:
            return self.rpc_url

        for chain_cfg in CHAIN_CONFIGS.values():
            if chain_cfg.chain_id == chain_id:
                return chain_cfg.rpc_url

        return None

    def _get_chain_config_for_id(self, chain_id: int) -> ChainConfig | None:
        """Get chain config for a specific chain ID."""
        for chain_cfg in CHAIN_CONFIGS.values():
            if chain_cfg.chain_id == chain_id:
                return chain_cfg
        return None

    def _encode_safe_exec_transaction(
        self,
        to: str,
        value: int,
        data: bytes,
        signature: bytes | None = None,
    ) -> bytes:
        """Encode a Safe execTransaction call.

        Args:
            to: Target address
            value: ETH value to send
            data: Call data
            signature: Optional ECDSA signature. If not provided, uses pre-validated
                       signature format (requires msg.sender == owner).
        """
        # execTransaction(address to, uint256 value, bytes data, uint8 operation,
        #                 uint256 safeTxGas, uint256 baseGas, uint256 gasPrice,
        #                 address gasToken, address refundReceiver, bytes signatures)
        exec_selector = keccak(
            text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
        )[:4]

        if signature is not None:
            # Use the provided ECDSA signature
            signatures = signature
        else:
            # For owner execution, we use a pre-validated signature
            # This is the signature format for msg.sender == owner
            signatures = bytes.fromhex(
                self.privy_wallet_address[2:].lower().zfill(64)  # r = owner address
                + "0" * 64  # s = 0
                + "01"  # v = 1 (indicates approved hash)
            )

        exec_data = encode(
            [
                "address",
                "uint256",
                "bytes",
                "uint8",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "bytes",
            ],
            [
                to_checksum_address(to),
                value,
                data,
                0,  # operation (0 = Call)
                0,  # safeTxGas
                0,  # baseGas
                0,  # gasPrice
                "0x0000000000000000000000000000000000000000",  # gasToken
                "0x0000000000000000000000000000000000000000",  # refundReceiver
                signatures,
            ],
        )

        return exec_selector + exec_data

    async def _get_allowance_nonce(
        self,
        rpc_url: str,
        allowance_module: str,
        token_address: str,
    ) -> int:
        """Get the current nonce for an allowance."""
        # getTokenAllowance(address safe, address delegate, address token)
        selector = keccak(text="getTokenAllowance(address,address,address)")[:4]
        call_data = selector + encode(
            ["address", "address", "address"],
            [self.safe_address, self.privy_wallet_address, token_address],
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": allowance_module, "data": "0x" + call_data.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to get allowance")

            result = response.json().get("result", "0x")
            # Result is uint256[5]: [amount, spent, resetTimeMin, lastResetMin, nonce]
            if len(result) >= 322:  # 2 + 5 * 64
                nonce_hex = result[258:322]  # 5th element
                return int(nonce_hex, 16)
            return 0

    async def _generate_transfer_hash(
        self,
        rpc_url: str,
        allowance_module: str,
        token_address: str,
        to: str,
        amount: int,
        nonce: int,
    ) -> bytes:
        """Generate the hash for an allowance transfer."""
        # generateTransferHash(address safe, address token, address to, uint96 amount,
        #                      address paymentToken, uint96 payment, uint16 nonce)
        selector = keccak(
            text="generateTransferHash(address,address,address,uint96,address,uint96,uint16)"
        )[:4]
        call_data = selector + encode(
            ["address", "address", "address", "uint96", "address", "uint96", "uint16"],
            [
                self.safe_address,
                to_checksum_address(token_address),
                to_checksum_address(to),
                amount,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                nonce,
            ],
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": allowance_module, "data": "0x" + call_data.hex()},
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise IntentKitAPIError(500, "RPCError", "Failed to generate hash")

            result = response.json().get("result", "0x")
            return bytes.fromhex(result[2:])

    def _encode_execute_allowance_transfer(
        self,
        token_address: str,
        to: str,
        amount: int,
        signature: str,
    ) -> bytes:
        """Encode executeAllowanceTransfer call."""
        # executeAllowanceTransfer(address safe, address token, address to, uint96 amount,
        #                          address paymentToken, uint96 payment, address delegate, bytes signature)
        selector = keccak(
            text="executeAllowanceTransfer(address,address,address,uint96,address,uint96,address,bytes)"
        )[:4]

        sig_bytes = bytes.fromhex(
            signature[2:] if signature.startswith("0x") else signature
        )

        exec_data = encode(
            [
                "address",
                "address",
                "address",
                "uint96",
                "address",
                "uint96",
                "address",
                "bytes",
            ],
            [
                self.safe_address,
                to_checksum_address(token_address),
                to_checksum_address(to),
                amount,
                "0x0000000000000000000000000000000000000000",  # paymentToken
                0,  # payment
                self.privy_wallet_address,  # delegate
                sig_bytes,
            ],
        )

        return selector + exec_data


# =============================================================================
# Safe Deployment and Setup Functions
# =============================================================================


async def deploy_safe_with_allowance(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    privy_wallet_address: str,
    network_id: str,
    rpc_url: str,
    weekly_spending_limit_usdc: float | None = None,
) -> dict[str, Any]:
    """
    Deploy a Safe smart account and configure the Allowance Module.

    This function:
    1. Deploys a new Safe with the Privy wallet as owner
    2. Enables the Allowance Module
    3. Adds the Privy wallet as a delegate
    4. Sets up weekly USDC spending limit if specified

    Args:
        privy_client: Initialized Privy client
        privy_wallet_id: Privy wallet ID
        privy_wallet_address: Privy wallet EOA address
        network_id: Network identifier (e.g., "base-mainnet")
        rpc_url: RPC URL for the network
        weekly_spending_limit_usdc: Weekly USDC spending limit (optional)

    Returns:
        dict with deployment info including safe_address and tx_hashes
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    safe_client = SafeClient(network_id, rpc_url)
    owner_address = to_checksum_address(privy_wallet_address)

    # Calculate salt nonce from wallet address for determinism
    salt_nonce = int.from_bytes(keccak(text=privy_wallet_id)[:8], "big")

    # Predict the Safe address
    predicted_address = safe_client.predict_safe_address(
        owner_address=owner_address,
        salt_nonce=salt_nonce,
        threshold=1,
    )

    result: dict[str, Any] = {
        "safe_address": predicted_address,
        "owner_address": owner_address,
        "network_id": network_id,
        "chain_id": chain_config.chain_id,
        "salt_nonce": salt_nonce,
        "tx_hashes": [],
        "allowance_module_enabled": False,
        "spending_limit_configured": False,
    }

    # Check if already deployed
    is_deployed = await safe_client.is_deployed(predicted_address, rpc_url)
    if is_deployed:
        logger.info(f"Safe already deployed at {predicted_address}")
        result["already_deployed"] = True
    else:
        # Deploy the Safe
        logger.info(f"Deploying Safe to {predicted_address}")
        deploy_tx_hash, actual_address = await _deploy_safe(
            owner_address=owner_address,
            salt_nonce=salt_nonce,
            chain_id=chain_config.chain_id,
            rpc_url=rpc_url,
        )
        result["tx_hashes"].append({"deploy_safe": deploy_tx_hash})
        result["already_deployed"] = False

        # Validate that predicted address matches actual deployed address
        if actual_address.lower() != predicted_address.lower():
            raise IntentKitAPIError(
                500,
                "AddressMismatch",
                f"Safe address prediction mismatch: predicted {predicted_address}, "
                f"but actually deployed to {actual_address}. "
                "This indicates a bug in the CREATE2 address calculation.",
            )
        logger.info(f"Safe address validated: {predicted_address}")

    # Enable Allowance Module if spending limit is configured
    if weekly_spending_limit_usdc is not None and weekly_spending_limit_usdc > 0:
        # Check if module is already enabled
        module_enabled = await _is_module_enabled(
            rpc_url=rpc_url,
            safe_address=predicted_address,
            module_address=chain_config.allowance_module_address,
        )

        if not module_enabled:
            logger.info("Enabling Allowance Module")
            enable_tx_hash = await _enable_allowance_module(
                privy_client=privy_client,
                privy_wallet_id=privy_wallet_id,
                safe_address=predicted_address,
                owner_address=owner_address,
                allowance_module_address=chain_config.allowance_module_address,
                chain_id=chain_config.chain_id,
                rpc_url=rpc_url,
            )
            result["tx_hashes"].append({"enable_module": enable_tx_hash})

        result["allowance_module_enabled"] = True

        # Configure spending limit
        if chain_config.usdc_address:
            logger.info(
                f"Setting weekly spending limit: {weekly_spending_limit_usdc} USDC"
            )
            limit_tx_hash = await _set_spending_limit(
                privy_client=privy_client,
                privy_wallet_id=privy_wallet_id,
                safe_address=predicted_address,
                owner_address=owner_address,
                delegate_address=owner_address,  # Privy wallet is the delegate
                token_address=chain_config.usdc_address,
                allowance_amount=int(
                    weekly_spending_limit_usdc * 1_000_000
                ),  # USDC has 6 decimals
                reset_time_minutes=7 * 24 * 60,  # 1 week in minutes
                allowance_module_address=chain_config.allowance_module_address,
                chain_id=chain_config.chain_id,
                rpc_url=rpc_url,
            )
            result["tx_hashes"].append({"set_spending_limit": limit_tx_hash})
            result["spending_limit_configured"] = True

    return result


async def _deploy_safe(
    owner_address: str,
    salt_nonce: int,
    chain_id: int,
    rpc_url: str,
) -> tuple[str, str]:
    """Deploy a new Safe via the ProxyFactory using master wallet.

    The master wallet pays for gas, but the Safe is owned by owner_address.
    This allows creating Safes for Privy wallets without them needing gas.

    Args:
        owner_address: The address that will own the Safe (Privy wallet address)
        salt_nonce: Salt for deterministic address generation
        chain_id: The chain ID to deploy on
        rpc_url: RPC URL for the chain

    Returns:
        Tuple of (transaction_hash, deployed_safe_address)
    """
    if not config.master_wallet_private_key:
        raise IntentKitAPIError(
            500,
            "ConfigError",
            "MASTER_WALLET_PRIVATE_KEY not configured. "
            "A master wallet is required to pay for Safe deployments.",
        )

    # Build initializer
    safe_client = SafeClient()
    initializer = safe_client._build_safe_initializer(
        owners=[owner_address],
        threshold=1,
    )

    # Encode createProxyWithNonce call
    create_selector = keccak(text="createProxyWithNonce(address,bytes,uint256)")[:4]
    create_data = create_selector + encode(
        ["address", "bytes", "uint256"],
        [SAFE_SINGLETON_ADDRESS, initializer, salt_nonce],
    )

    # Use master wallet to send transaction
    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    master_account = Account.from_key(config.master_wallet_private_key)

    logger.info(
        f"Deploying Safe for owner {owner_address} using master wallet {master_account.address}"
    )

    # Build transaction
    nonce = await w3.eth.get_transaction_count(master_account.address)
    gas_price = await w3.eth.gas_price

    tx: dict[str, Any] = {
        "from": master_account.address,
        "to": SAFE_PROXY_FACTORY_ADDRESS,
        "value": 0,
        "data": create_data,
        "nonce": nonce,
        "chainId": chain_id,
        "gas": 500000,  # Safe deployment typically needs ~300k gas
        "gasPrice": gas_price,
    }

    # Estimate gas
    try:
        estimated_gas = await w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated_gas * 1.2)  # Add 20% buffer
        logger.debug(f"Estimated gas for Safe deployment: {estimated_gas}")
    except Exception as e:
        logger.warning(f"Gas estimation failed, using default 500000: {e}")

    # Sign and send
    signed_tx = master_account.sign_transaction(tx)
    tx_hash = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    logger.info(f"Safe deployment tx sent: {tx_hash.hex()}")

    # Wait for confirmation
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise IntentKitAPIError(
            500, "DeploymentFailed", "Safe deployment transaction failed"
        )

    # Extract the deployed Safe address from ProxyCreation event
    # Event signature: ProxyCreation(address proxy, address singleton)
    # Topic: keccak256("ProxyCreation(address,address)")
    proxy_creation_topic = keccak(text="ProxyCreation(address,address)").hex()
    actual_safe_address: str | None = None

    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if topics and topics[0].hex() == proxy_creation_topic:
            # The proxy address is in the event data (first 32 bytes, padded)
            log_data = log.get("data", b"")
            # Handle both bytes and HexBytes types
            if hasattr(log_data, "hex"):
                # It's bytes or HexBytes, convert to bytes
                log_data = bytes(log_data)
            elif isinstance(log_data, str):
                log_data = bytes.fromhex(
                    log_data[2:] if log_data.startswith("0x") else log_data
                )
            if len(log_data) >= 32:
                # Extract address from first 32 bytes (last 20 bytes are the address)
                actual_safe_address = to_checksum_address(log_data[12:32])
                break

    if not actual_safe_address:
        raise IntentKitAPIError(
            500,
            "DeploymentFailed",
            "Could not extract deployed Safe address from ProxyCreation event",
        )

    logger.info(
        f"Safe deployed successfully. Tx hash: {tx_hash.hex()}, "
        f"Gas used: {receipt['gasUsed']}, Address: {actual_safe_address}"
    )

    return tx_hash.hex(), actual_safe_address


async def _is_module_enabled(
    rpc_url: str,
    safe_address: str,
    module_address: str,
) -> bool:
    """Check if a module is enabled on a Safe."""
    # isModuleEnabled(address module)
    selector = keccak(text="isModuleEnabled(address)")[:4]
    call_data = selector + encode(["address"], [module_address])

    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": safe_address, "data": "0x" + call_data.hex()},
                    "latest",
                ],
                "id": 1,
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            return False

        result = response.json().get("result", "0x")
        return result.endswith("1")


def _get_safe_tx_hash(
    safe_address: str,
    to: str,
    value: int,
    data: bytes,
    nonce: int,
    chain_id: int,
) -> bytes:
    """Calculate the Safe transaction hash for signing.

    This generates the EIP-712 typed data hash that owners must sign.
    """
    # Domain separator
    domain_type_hash = keccak(
        text="EIP712Domain(uint256 chainId,address verifyingContract)"
    )
    domain_separator = keccak(
        domain_type_hash
        + encode(["uint256", "address"], [chain_id, to_checksum_address(safe_address)])
    )

    # Safe tx type hash
    safe_tx_type_hash = keccak(
        text="SafeTx(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,uint256 nonce)"
    )

    # Encode the transaction data
    data_hash = keccak(data)
    safe_tx_hash_data = encode(
        [
            "bytes32",
            "address",
            "uint256",
            "bytes32",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "uint256",
        ],
        [
            safe_tx_type_hash,
            to_checksum_address(to),
            value,
            data_hash,
            0,  # operation
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            nonce,
        ],
    )
    struct_hash = keccak(safe_tx_hash_data)

    # Final hash: keccak256("\x19\x01" + domainSeparator + structHash)
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


async def _get_safe_nonce(safe_address: str, rpc_url: str) -> int:
    """Get the current nonce of a Safe."""
    selector = keccak(text="nonce()")[:4]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": safe_address, "data": "0x" + selector.hex()},
                    "latest",
                ],
                "id": 1,
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise IntentKitAPIError(500, "RPCError", "Failed to get Safe nonce")

        result = response.json().get("result", "0x0")
        # Handle empty result '0x' as 0
        if result == "0x" or not result:
            return 0
        return int(result, 16)


async def _send_safe_transaction_with_master_wallet(
    safe_address: str,
    exec_data: bytes,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Send a Safe transaction using master wallet to pay for gas.

    This function sends a pre-encoded Safe execTransaction call using the
    master wallet to pay for gas. The transaction must already be properly
    signed by the Safe owner.

    Args:
        safe_address: The Safe contract address
        exec_data: Encoded execTransaction call data (including signatures)
        chain_id: Chain ID
        rpc_url: RPC URL

    Returns:
        Transaction hash
    """
    if not config.master_wallet_private_key:
        raise IntentKitAPIError(
            500,
            "ConfigError",
            "MASTER_WALLET_PRIVATE_KEY not configured",
        )

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    master_account = Account.from_key(config.master_wallet_private_key)

    nonce = await w3.eth.get_transaction_count(master_account.address)
    gas_price = await w3.eth.gas_price

    tx: dict[str, Any] = {
        "from": master_account.address,
        "to": safe_address,
        "value": 0,
        "data": exec_data,
        "nonce": nonce,
        "chainId": chain_id,
        "gas": 300000,
        "gasPrice": gas_price,
    }

    try:
        estimated_gas = await w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated_gas * 1.2)
    except Exception as e:
        logger.warning(f"Gas estimation failed for Safe tx, using default: {e}")

    signed_tx = master_account.sign_transaction(tx)
    tx_hash = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise IntentKitAPIError(500, "SafeTxFailed", "Safe transaction failed")

    return tx_hash.hex()


async def _enable_allowance_module(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    owner_address: str,
    allowance_module_address: str,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Enable the Allowance Module on a Safe using master wallet for gas.

    The Privy wallet signs the Safe transaction, and the master wallet
    pays for the gas to submit it on-chain.
    """
    # enableModule(address module)
    enable_selector = keccak(text="enableModule(address)")[:4]
    enable_data = enable_selector + encode(["address"], [allowance_module_address])

    # Get Safe nonce for signing
    safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=safe_address,  # Call Safe itself to enable module
        value=0,
        data=enable_data,
        nonce=safe_nonce,
        chain_id=chain_id,
    )

    # Sign the transaction hash with Privy wallet
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    # Safe expects v to be 27 or 28, but some signers return 0 or 1
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with the signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            to_checksum_address(safe_address),  # to: Safe itself
            0,  # value
            enable_data,  # data
            0,  # operation: 0 = Call
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use master wallet to send the transaction
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_id,
        rpc_url=rpc_url,
    )

    return tx_hash


async def _set_spending_limit(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    owner_address: str,
    delegate_address: str,
    token_address: str,
    allowance_amount: int,
    reset_time_minutes: int,
    allowance_module_address: str,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Set a spending limit via the Allowance Module using master wallet for gas.

    The Privy wallet signs the Safe transaction, and the master wallet
    pays for the gas to submit it on-chain.
    """
    # First, add delegate: addDelegate(address delegate)
    add_delegate_selector = keccak(text="addDelegate(address)")[:4]
    add_delegate_data = add_delegate_selector + encode(["address"], [delegate_address])

    # Then, set allowance: setAllowance(address delegate, address token, uint96 allowanceAmount, uint16 resetTimeMin, uint32 resetBaseMin)
    set_allowance_selector = keccak(
        text="setAllowance(address,address,uint96,uint16,uint32)"
    )[:4]
    set_allowance_data = set_allowance_selector + encode(
        ["address", "address", "uint96", "uint16", "uint32"],
        [
            delegate_address,
            token_address,
            allowance_amount,
            reset_time_minutes,
            0,  # resetBaseMin
        ],
    )

    # Use MultiSend to batch both calls
    # Encode for MultiSend: operation (1 byte) + to (20 bytes) + value (32 bytes) + dataLength (32 bytes) + data
    def encode_multi_send_tx(to: str, value: int, data: bytes) -> bytes:
        return (
            bytes([0])  # operation: 0 = Call
            + bytes.fromhex(to[2:])  # to address
            + value.to_bytes(32, "big")  # value
            + len(data).to_bytes(32, "big")  # data length
            + data  # data
        )

    multi_send_txs = encode_multi_send_tx(
        allowance_module_address, 0, add_delegate_data
    ) + encode_multi_send_tx(allowance_module_address, 0, set_allowance_data)

    # multiSend(bytes transactions)
    multi_send_selector = keccak(text="multiSend(bytes)")[:4]
    multi_send_data = multi_send_selector + encode(["bytes"], [multi_send_txs])

    # Get Safe nonce for signing
    safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash for the MultiSend call
    # Note: We use MULTI_SEND_CALL_ONLY_ADDRESS with DelegateCall
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=MULTI_SEND_CALL_ONLY_ADDRESS,
        value=0,
        data=multi_send_data,
        nonce=safe_nonce,
        chain_id=chain_id,
    )

    # Sign the transaction hash with Privy wallet
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            MULTI_SEND_CALL_ONLY_ADDRESS,  # to
            0,  # value
            multi_send_data,  # data
            1,  # operation: 1 = DelegateCall for MultiSend
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use master wallet to send the transaction
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_id,
        rpc_url=rpc_url,
    )

    return tx_hash


# =============================================================================
# Gasless Transaction Support (Relayer Pattern)
# =============================================================================


async def execute_gasless_transaction(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    to: str,
    value: int,
    data: bytes,
    network_id: str,
    rpc_url: str,
) -> str:
    """
    Execute a Safe transaction with gas paid by the Master Wallet (Relayer pattern).

    This enables gasless transactions for Safe wallets:
    1. The Safe owner (Privy wallet) signs the transaction hash off-chain
    2. The Master Wallet submits the signed transaction on-chain and pays for gas
    3. The Safe executes the transaction

    This is ideal for scenarios where Safe wallet owners don't hold ETH for gas,
    such as User-to-Agent USDC transfers.

    Args:
        privy_client: Initialized Privy client
        privy_wallet_id: The Privy wallet ID (owner of the Safe)
        safe_address: The Safe smart account address
        to: Target address for the transaction
        value: ETH value to send (in wei, usually 0 for ERC20 transfers)
        data: Transaction calldata (e.g., encoded ERC20 transfer)
        network_id: Network identifier (e.g., "base-mainnet")
        rpc_url: RPC URL for the network

    Returns:
        Transaction hash of the executed transaction

    Raises:
        ValueError: If network is not supported
        IntentKitAPIError: If transaction execution fails
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Get Safe nonce for signing
    safe_nonce = await _get_safe_nonce(safe_address, rpc_url)

    # Calculate Safe transaction hash (EIP-712)
    safe_tx_hash = _get_safe_tx_hash(
        safe_address=safe_address,
        to=to,
        value=value,
        data=data,
        nonce=safe_nonce,
        chain_id=chain_config.chain_id,
    )

    # Sign the transaction hash with Privy wallet (off-chain, no gas)
    signature_hex = await privy_client.sign_hash(privy_wallet_id, safe_tx_hash)

    # Parse signature and adjust v value for Safe
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]
    # Safe expects v to be 27 or 28, but some signers return 0 or 1
    if v < 27:
        v += 27
    signature = r + s + bytes([v])

    # Encode execTransaction with the signature
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    exec_data = exec_selector + encode(
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [
            to_checksum_address(to),
            value,
            data,
            0,  # operation: 0 = Call
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signature,
        ],
    )

    # Use Master Wallet to relay the transaction (pays for gas)
    tx_hash = await _send_safe_transaction_with_master_wallet(
        safe_address=safe_address,
        exec_data=exec_data,
        chain_id=chain_config.chain_id,
        rpc_url=rpc_url,
    )

    logger.info(
        f"Gasless transaction executed: Safe={safe_address}, To={to}, Value={value}, TxHash={tx_hash}"
    )

    return tx_hash


async def transfer_erc20_gasless(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    token_address: str,
    to: str,
    amount: int,
    network_id: str,
    rpc_url: str,
) -> str:
    """
    Transfer ERC20 tokens from a Safe wallet with gas paid by Master Wallet.

    This is a convenience wrapper around execute_gasless_transaction for
    ERC20 token transfers. Ideal for USDC transfers between User and Agent wallets.

    Args:
        privy_client: Initialized Privy client
        privy_wallet_id: The Privy wallet ID (owner of the Safe)
        safe_address: The Safe smart account address
        token_address: The ERC20 token contract address
        to: Recipient address
        amount: Amount to transfer (in token's smallest unit, e.g., 6 decimals for USDC)
        network_id: Network identifier (e.g., "base-mainnet")
        rpc_url: RPC URL for the network

    Returns:
        Transaction hash of the executed transfer

    Example:
        # Transfer 10 USDC from User Safe to Agent Safe
        tx_hash = await transfer_erc20_gasless(
            privy_client=privy_client,
            privy_wallet_id=user_privy_wallet_id,
            safe_address=user_safe_address,
            token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
            to=agent_safe_address,
            amount=10_000_000,  # 10 USDC (6 decimals)
            network_id="base-mainnet",
            rpc_url=rpc_url,
        )
    """
    # Encode ERC20 transfer call
    transfer_selector = keccak(text="transfer(address,uint256)")[:4]
    transfer_data = transfer_selector + encode(
        ["address", "uint256"],
        [to_checksum_address(to), amount],
    )

    return await execute_gasless_transaction(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet_id,
        safe_address=safe_address,
        to=to_checksum_address(token_address),
        value=0,
        data=transfer_data,
        network_id=network_id,
        rpc_url=rpc_url,
    )


# =============================================================================
# Main Entry Points
# =============================================================================


async def create_privy_safe_wallet(
    agent_id: str,
    network_id: str = "base-mainnet",
    rpc_url: str | None = None,
    weekly_spending_limit_usdc: float | None = None,
    existing_privy_wallet_id: str | None = None,
    existing_privy_wallet_address: str | None = None,
) -> dict[str, Any]:
    """
    Create a Privy server wallet and deploy a Safe smart account.

    This is the main entry point for creating a new agent wallet with
    Safe smart account and optional spending limits.

    Supports recovery mode: if a previous attempt created a Privy wallet but
    failed to deploy the Safe, pass the existing wallet details to resume
    without creating a duplicate Privy wallet.

    Args:
        agent_id: Unique identifier for the agent (used as idempotency key)
        network_id: The network to use (default: base-mainnet)
        rpc_url: Optional RPC URL override
        weekly_spending_limit_usdc: Optional weekly USDC spending limit
        existing_privy_wallet_id: Existing Privy wallet ID for recovery mode
        existing_privy_wallet_address: Existing Privy wallet address for recovery mode

    Returns:
        dict: Metadata including:
            - privy_wallet_id: The Privy wallet ID
            - privy_wallet_address: The Privy EOA address (owner/signer)
            - smart_wallet_address: The Safe smart account address
            - provider: "safe"
            - network_id: The network ID
            - chain_id: The chain ID
            - deployment_info: Deployment transaction details
    """
    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Get RPC URL
    effective_rpc_url = rpc_url or chain_config.rpc_url
    if not effective_rpc_url:
        raise ValueError(f"No RPC URL configured for {network_id}")

    privy_client = PrivyClient()

    # 1. Get or create Privy Wallet (EOA that will own the Safe)
    # Recovery mode: use existing wallet if provided (avoids creating duplicate wallets)
    if existing_privy_wallet_id and existing_privy_wallet_address:
        logger.info(
            f"Recovery mode: using existing Privy wallet {existing_privy_wallet_id}"
        )
        privy_wallet_id = existing_privy_wallet_id
        privy_wallet_address = existing_privy_wallet_address
    else:
        privy_wallet = await privy_client.create_wallet()
        privy_wallet_id = privy_wallet.id
        privy_wallet_address = privy_wallet.address

    # 2. Deploy Safe and configure allowance module
    deployment_info = await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=privy_wallet_address,
        network_id=network_id,
        rpc_url=effective_rpc_url,
        weekly_spending_limit_usdc=weekly_spending_limit_usdc,
    )

    return {
        "privy_wallet_id": privy_wallet_id,
        "privy_wallet_address": privy_wallet_address,
        "smart_wallet_address": deployment_info["safe_address"],
        "provider": "safe",
        "network_id": network_id,
        "chain_id": chain_config.chain_id,
        "salt_nonce": deployment_info["salt_nonce"],
        "deployment_info": deployment_info,
    }


def get_wallet_provider(
    privy_wallet_data: dict[str, Any],
    rpc_url: str | None = None,
) -> SafeWalletProvider:
    """
    Create a SafeWalletProvider from stored wallet data.

    This is used to restore a wallet provider from persisted agent data.

    Args:
        privy_wallet_data: The stored wallet metadata
        rpc_url: Optional RPC URL override

    Returns:
        SafeWalletProvider instance ready for transactions
    """
    return SafeWalletProvider(
        privy_wallet_id=privy_wallet_data["privy_wallet_id"],
        privy_wallet_address=privy_wallet_data["privy_wallet_address"],
        safe_address=privy_wallet_data["smart_wallet_address"],
        network_id=privy_wallet_data.get("network_id", "base-mainnet"),
        rpc_url=rpc_url,
    )


# =============================================================================
# Privy Wallet Signer (eth_account compatible)
# =============================================================================


class PrivyWalletSigner:
    """
    EVM wallet signer that adapts Privy's API to eth_account interface.

    This allows Privy wallets to be used with libraries expecting
    standard EVM signer interfaces (like x402, web3.py, etc.).

    The signer uses the Privy EOA for signing, which is the actual
    key holder. For x402 payments, the signature comes from this EOA.

    Note: This class uses threading to run async Privy API calls
    synchronously, avoiding nested event loop issues when called
    from within an existing async context.
    """

    def __init__(
        self,
        privy_client: PrivyClient,
        wallet_id: str,
        wallet_address: str,
    ) -> None:
        """
        Initialize the Privy wallet signer.

        Args:
            privy_client: The Privy client for API calls.
            wallet_id: The Privy wallet ID.
            wallet_address: The EOA wallet address (used for signing).
        """
        self.privy_client = privy_client
        self.wallet_id = wallet_id
        self._address = to_checksum_address(wallet_address)

    @property
    def address(self) -> str:
        """The wallet address used for signing (EOA address)."""
        return self._address

    def _run_in_thread(self, coro: Any) -> Any:
        """
        Run an async coroutine in a separate thread.

        This avoids nested event loop errors when called from
        within an existing async context.

        Args:
            coro: The coroutine to run.

        Returns:
            The result of the coroutine.

        Raises:
            Any exception raised by the coroutine.
        """
        import asyncio
        import threading

        result: list[Any] = []
        error: list[BaseException] = []

        def _target() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result.append(loop.run_until_complete(coro))
                finally:
                    loop.close()
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if error:
            raise error[0]
        return result[0] if result else None

    def sign_message(self, signable_message: Any) -> Any:
        """
        Sign a message (EIP-191 personal_sign).

        Args:
            signable_message: The message to sign. Can be:
                - A string message
                - An eth_account.messages.SignableMessage
                - A bytes object

        Returns:
            SignedMessage-like object with v, r, s, and signature attributes.
        """
        from eth_account.datastructures import SignedMessage
        from eth_account.messages import encode_defunct

        # Handle different message types
        if hasattr(signable_message, "body"):
            # It's a SignableMessage, extract the body
            message_text = signable_message.body.decode("utf-8")
        elif isinstance(signable_message, bytes):
            message_text = signable_message.decode("utf-8")
        elif isinstance(signable_message, str):
            message_text = signable_message
        else:
            # Try to convert to string
            message_text = str(signable_message)

        # Sign via Privy
        signature_hex = self._run_in_thread(
            self.privy_client.sign_message(self.wallet_id, message_text)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s from signature
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        # Create message hash for the SignedMessage
        message_for_hash = encode_defunct(text=message_text)

        try:
            from eth_account.messages import _hash_eip191_message

            message_hash = _hash_eip191_message(message_for_hash)
        except ImportError:
            # Fallback for older eth_account versions
            from eth_account._utils.signing import hash_eip191_message

            message_hash = hash_eip191_message(message_for_hash)

        return SignedMessage(
            messageHash=message_hash,
            r=r,
            s=s,
            v=v,
            signature=signature_bytes,
        )

    def sign_typed_data(
        self,
        domain_data: dict[str, Any] | None = None,
        message_types: dict[str, Any] | None = None,
        message_data: dict[str, Any] | None = None,
        full_message: dict[str, Any] | None = None,
    ) -> Any:
        """
        Sign typed data (EIP-712).

        Args:
            domain_data: The EIP-712 domain data.
            message_types: The type definitions.
            message_data: The message data to sign.
            full_message: Alternative: the complete typed data structure.

        Returns:
            SignedMessage-like object with signature.
        """
        from eth_account.datastructures import SignedMessage

        # Build the typed data structure
        if full_message is not None:
            typed_data = full_message
        else:
            typed_data = {
                "domain": domain_data or {},
                "types": message_types or {},
                "message": message_data or {},
                "primaryType": message_types.get("primaryType", "Message")
                if message_types
                else "Message",
            }

        # Sign via Privy
        signature_hex = self._run_in_thread(
            self.privy_client.sign_typed_data(self.wallet_id, typed_data)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        return SignedMessage(
            messageHash=b"\x00" * 32,  # Placeholder, actual hash computation is complex
            r=r,
            s=s,
            v=v,
            signature=signature_bytes,
        )

    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        """
        Sign a raw hash directly (unsafe, use with caution).

        This method signs a hash without any prefix or encoding.
        It uses personal_sign with the hex-encoded hash as the message.

        Args:
            message_hash: The 32-byte hash to sign. Can be bytes or HexBytes.

        Returns:
            SignedMessage-like object with signature.
        """
        from eth_account.datastructures import SignedMessage

        # Convert to bytes if needed
        if hasattr(message_hash, "hex"):
            hash_bytes = bytes(message_hash)
        elif isinstance(message_hash, bytes):
            hash_bytes = message_hash
        else:
            hash_bytes = bytes.fromhex(str(message_hash).replace("0x", ""))

        # Sign via Privy using sign_hash
        signature_hex = self._run_in_thread(
            self.privy_client.sign_hash(self.wallet_id, hash_bytes)
        )

        # Parse the signature
        signature_bytes = bytes.fromhex(signature_hex.replace("0x", ""))

        # Extract v, r, s
        r = int.from_bytes(signature_bytes[:32], "big")
        s = int.from_bytes(signature_bytes[32:64], "big")
        v = signature_bytes[64]

        return SignedMessage(
            messageHash=hash_bytes,
            r=r,
            s=s,
            v=v,
            signature=signature_bytes,
        )

    def sign_transaction(self, transaction_dict: dict[str, Any]) -> Any:
        """
        Sign a transaction.

        Note: For Privy with Safe wallets, transactions are typically
        executed through the Safe rather than signed directly.
        This method is provided for interface compatibility.

        Args:
            transaction_dict: The transaction dictionary to sign.

        Returns:
            Signed transaction.

        Raises:
            NotImplementedError: Direct transaction signing is not supported.
                Use SafeWalletProvider.execute_transaction instead.
        """
        raise NotImplementedError(
            "Direct transaction signing is not supported for Privy wallets. "
            "Use SafeWalletProvider.execute_transaction() to execute transactions "
            "through the Safe smart account."
        )


def get_wallet_signer(
    privy_wallet_data: dict[str, Any],
) -> PrivyWalletSigner:
    """
    Create a PrivyWalletSigner from stored wallet data.

    This is used to get a signer for operations that require
    direct signing (like x402 payments).

    Args:
        privy_wallet_data: The stored wallet metadata containing
            privy_wallet_id and privy_wallet_address.

    Returns:
        PrivyWalletSigner instance ready for signing.
    """
    privy_client = PrivyClient()
    return PrivyWalletSigner(
        privy_client=privy_client,
        wallet_id=privy_wallet_data["privy_wallet_id"],
        wallet_address=privy_wallet_data["privy_wallet_address"],
    )
