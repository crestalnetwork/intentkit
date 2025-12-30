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
from eth_utils import keccak, to_checksum_address
from pydantic import BaseModel

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

    async def create_wallet(self, idempotency_key: str | None = None) -> PrivyWallet:
        """Create a new server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets"
        payload: dict[str, Any] = {
            "chain_type": "ethereum",
        }
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key

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
        """Sign a message using the Privy server wallet (personal_sign)."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "personal_sign",
            "params": {
                "message": message,
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
        """Sign a hash directly using the Privy server wallet."""
        if not self.app_id or not self.app_secret:
            raise IntentKitAPIError(
                500, "PrivyConfigError", "Privy credentials missing"
            )

        # Privy expects the hash as a hex string with 0x prefix
        hash_hex = "0x" + hash_bytes.hex()

        url = f"{self.base_url}/wallets/{wallet_id}/rpc"
        payload = {
            "method": "personal_sign",
            "params": {
                "message": hash_hex,
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
        """Calculate the CREATE2 address for a Safe deployment."""
        # Salt is keccak256(keccak256(initializer) + salt_nonce)
        initializer_hash = keccak(initializer)
        salt = keccak(initializer_hash + encode(["uint256"], [salt_nonce]))

        # Proxy creation code (Safe v1.3.0 GnosisSafeProxyFactory)
        # This is the bytecode that deploys a minimal proxy pointing to the singleton
        proxy_creation_code = bytes.fromhex(
            "608060405234801561001057600080fd5b506040516101e63803806101e68339818101604052602081101561003357600080fd5b8101908080519060200190929190505050600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614156100ca576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806101c46022913960400191505060405180910390fd5b806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055505060ab806101196000396000f3fe608060405273ffffffffffffffffffffffffffffffffffffffff600054167fa619486e0000000000000000000000000000000000000000000000000000000060003514156050578060005260206000f35b3660008037600080366000845af43d6000803e60008114156070573d6000fd5b3d6000f3fea2646970667358221220d1429297349653a4918076d650332de1a1068c5f3e07c5c82360c277770b955264736f6c63430007060033496e76616c69642073696e676c65746f6e20616464726573732070726f7669646564"
        )

        # The init code is the creation code + encoded singleton address
        init_code = proxy_creation_code + encode(["address"], [SAFE_SINGLETON_ADDRESS])

        # deploymentData for CREATE2: keccak256(init_code + initializer)
        deployment_data = init_code + initializer
        init_code_hash = keccak(deployment_data)

        # CREATE2 address calculation
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
    ) -> bytes:
        """Encode a Safe execTransaction call."""
        # execTransaction(address to, uint256 value, bytes data, uint8 operation,
        #                 uint256 safeTxGas, uint256 baseGas, uint256 gasPrice,
        #                 address gasToken, address refundReceiver, bytes signatures)
        exec_selector = keccak(
            text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
        )[:4]

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
        deploy_tx_hash = await _deploy_safe(
            privy_client=privy_client,
            privy_wallet_id=privy_wallet_id,
            owner_address=owner_address,
            salt_nonce=salt_nonce,
            chain_id=chain_config.chain_id,
            rpc_url=rpc_url,
        )
        result["tx_hashes"].append({"deploy_safe": deploy_tx_hash})
        result["already_deployed"] = False

        # Wait for deployment (simple polling)
        await _wait_for_deployment(predicted_address, rpc_url)

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
    privy_client: PrivyClient,
    privy_wallet_id: str,
    owner_address: str,
    salt_nonce: int,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Deploy a new Safe via the ProxyFactory."""
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

    # Send transaction via Privy
    tx_hash = await privy_client.send_transaction(
        wallet_id=privy_wallet_id,
        chain_id=chain_id,
        to=SAFE_PROXY_FACTORY_ADDRESS,
        value=0,
        data="0x" + create_data.hex(),
    )

    return tx_hash


async def _wait_for_deployment(
    address: str,
    rpc_url: str,
    max_attempts: int = 30,
    delay_seconds: float = 2.0,
) -> bool:
    """Wait for a contract to be deployed."""
    import asyncio

    for _ in range(max_attempts):
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

            if response.status_code == 200:
                result = response.json().get("result", "0x")
                if len(result) > 2:
                    return True

        await asyncio.sleep(delay_seconds)

    raise IntentKitAPIError(
        500, "DeploymentTimeout", f"Safe deployment not confirmed at {address}"
    )


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


async def _enable_allowance_module(
    privy_client: PrivyClient,
    privy_wallet_id: str,
    safe_address: str,
    owner_address: str,
    allowance_module_address: str,
    chain_id: int,
    rpc_url: str,
) -> str:
    """Enable the Allowance Module on a Safe."""
    # enableModule(address module)
    enable_selector = keccak(text="enableModule(address)")[:4]
    enable_data = enable_selector + encode(["address"], [allowance_module_address])

    # Wrap in execTransaction
    provider = SafeWalletProvider(
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=owner_address,
        safe_address=safe_address,
    )

    exec_data = provider._encode_safe_exec_transaction(
        to=safe_address,  # Call Safe itself
        value=0,
        data=enable_data,
    )

    tx_hash = await privy_client.send_transaction(
        wallet_id=privy_wallet_id,
        chain_id=chain_id,
        to=safe_address,
        value=0,
        data="0x" + exec_data.hex(),
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
    """Set a spending limit via the Allowance Module."""
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

    # Wrap in execTransaction with DELEGATECALL operation
    # execTransaction with operation = 1 (DELEGATECALL)
    exec_selector = keccak(
        text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)"
    )[:4]

    # For owner execution, we use a pre-validated signature
    signatures = bytes.fromhex(
        owner_address[2:].lower().zfill(64)  # r = owner address
        + "0" * 64  # s = 0
        + "01"  # v = 1 (indicates approved hash)
    )

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
            1,  # operation (DELEGATECALL)
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            signatures,
        ],
    )

    tx_hash = await privy_client.send_transaction(
        wallet_id=privy_wallet_id,
        chain_id=chain_id,
        to=safe_address,
        value=0,
        data="0x" + exec_data.hex(),
    )

    return tx_hash


# =============================================================================
# Main Entry Points
# =============================================================================


async def create_privy_safe_wallet(
    agent_id: str,
    network_id: str = "base-mainnet",
    rpc_url: str | None = None,
    weekly_spending_limit_usdc: float | None = None,
) -> dict[str, Any]:
    """
    Create a Privy server wallet and deploy a Safe smart account.

    This is the main entry point for creating a new agent wallet with
    Safe smart account and optional spending limits.

    Args:
        agent_id: Unique identifier for the agent (used as idempotency key)
        network_id: The network to use (default: base-mainnet)
        rpc_url: Optional RPC URL override
        weekly_spending_limit_usdc: Optional weekly USDC spending limit

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

    # 1. Create Privy Wallet (EOA that will own the Safe)
    privy_wallet = await privy_client.create_wallet(idempotency_key=agent_id)

    # 2. Deploy Safe and configure allowance module
    deployment_info = await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet.id,
        privy_wallet_address=privy_wallet.address,
        network_id=network_id,
        rpc_url=effective_rpc_url,
        weekly_spending_limit_usdc=weekly_spending_limit_usdc,
    )

    return {
        "privy_wallet_id": privy_wallet.id,
        "privy_wallet_address": privy_wallet.address,
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
