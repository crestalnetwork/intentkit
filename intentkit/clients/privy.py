"""
Privy Client and Safe Smart Account Integration.

This module provides:
1. PrivyClient: Wrapper for Privy Server Wallet API
2. SafeClient: Utilities for Safe Smart Accounts (deployment, prediction)
3. SafeWalletProvider: Implementation of WalletProvider for Safe
4. Helper functions for creating and managing agent wallets

Refactored into smaller modules:
- privy_types.py: Type definitions and constants
- privy_utils.py: Utility functions
- privy_nonce.py: Nonce management
- privy_client.py: Privy API client
- privy_safe.py: Safe wallet logic and deployment
- privy_signer.py: Signer interface
"""

# Re-export everything to maintain backward compatibility
from intentkit.clients.privy_client import PrivyClient
from intentkit.clients.privy_nonce import (
    MasterWalletNonceManager,
    _get_nonce_manager,
)
from intentkit.clients.privy_safe import (
    SafeClient,
    SafeWalletProvider,
    _deploy_safe,
    _enable_allowance_module,
    _execute_allowance_transfer_gasless,
    _get_safe_nonce,
    _get_safe_tx_hash,
    _is_module_enabled,
    _send_safe_transaction_with_master_wallet,
    _send_transaction_with_master_wallet,
    _set_spending_limit,
    _wait_for_safe_deployed,
    create_privy_safe_wallet,
    deploy_safe_with_allowance,
    execute_gasless_transaction,
    get_wallet_provider,
    transfer_erc20_gasless,
)
from intentkit.clients.privy_signer import (
    PrivyWalletSigner,
    get_wallet_signer,
)
from intentkit.clients.privy_types import (
    CHAIN_CONFIGS,
    MULTI_SEND_ADDRESS,
    MULTI_SEND_CALL_ONLY_ADDRESS,
    SAFE_ABI,
    SAFE_FALLBACK_HANDLER_ADDRESS,
    SAFE_PROXY_FACTORY_ADDRESS,
    SAFE_SINGLETON_L2_CANONICAL,
    SAFE_SINGLETON_L2_EIP155,
    ChainConfig,
    PrivyWallet,
    TransactionRequest,
    TransactionResult,
    WalletProvider,
)
from intentkit.clients.privy_utils import (
    _canonicalize_json,
    _convert_typed_data_to_privy_format,
    _privy_private_key_to_pem,
    _sanitize_for_json,
)

__all__ = [
    "CHAIN_CONFIGS",
    "MULTI_SEND_ADDRESS",
    "MULTI_SEND_CALL_ONLY_ADDRESS",
    "SAFE_ABI",
    "SAFE_FALLBACK_HANDLER_ADDRESS",
    "SAFE_PROXY_FACTORY_ADDRESS",
    "SAFE_SINGLETON_L2_CANONICAL",
    "SAFE_SINGLETON_L2_EIP155",
    "ChainConfig",
    "MasterWalletNonceManager",
    "PrivyClient",
    "PrivyWallet",
    "PrivyWalletSigner",
    "SafeClient",
    "SafeWalletProvider",
    "TransactionRequest",
    "TransactionResult",
    "WalletProvider",
    "_canonicalize_json",
    "_convert_typed_data_to_privy_format",
    "_deploy_safe",
    "_enable_allowance_module",
    "_execute_allowance_transfer_gasless",
    "_get_nonce_manager",
    "_get_safe_nonce",
    "_get_safe_tx_hash",
    "_is_module_enabled",
    "_privy_private_key_to_pem",
    "_sanitize_for_json",
    "_send_safe_transaction_with_master_wallet",
    "_send_transaction_with_master_wallet",
    "_set_spending_limit",
    "_wait_for_safe_deployed",
    "create_privy_safe_wallet",
    "deploy_safe_with_allowance",
    "execute_gasless_transaction",
    "get_wallet_provider",
    "get_wallet_signer",
    "transfer_erc20_gasless",
]
