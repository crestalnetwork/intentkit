# AgentKit 0.4.0 → 0.6.0 Upgrade Guide

This guide covers the complete migration from **coinbase-agentkit 0.4.0** to **0.6.0**, including breaking changes, wallet compatibility fixes, and required updates.

## Quick Summary

- **Dependencies**: Updated AgentKit core and langchain packages
- **API Changes**: Wallet providers renamed, function signatures changed
- **Environment Variables**: New canonical names for CDP credentials
- **Wallet Compatibility**: Fixed invalid wallet addresses from format changes
- **Schema Updates**: Removed deprecated functions

## 1. Dependencies Updated

```toml
# Before (0.4.0)
coinbase-agentkit = "0.4.0"
coinbase-agentkit-langchain = "0.3.0"
langgraph = ">=0.4.3"

# After (0.6.0)
coinbase-agentkit = "0.6.0"
coinbase-agentkit-langchain = "0.5.0"
langgraph = ">=0.3.0"
pydantic = ">=2.10.0,<2.11.0"
```

## 2. Environment Variables

AgentKit 0.6.0 uses new environment variable names:

```bash
# New variables (0.6.0)
export CDP_API_KEY_ID="your_key_id"
export CDP_API_KEY_SECRET="your_private_key"
export CDP_WALLET_SECRET="your_wallet_secret"
```

## 3. Breaking API Changes

### Wallet Provider Classes
```python
# Before (0.4.0)
from coinbase_agentkit import CdpWalletProvider, CdpWalletProviderConfig

# After (0.6.0)
from coinbase_agentkit import CdpEvmServerWalletProvider, CdpEvmServerWalletProviderConfig
```

### Function Calls
```python
# Before (0.4.0)
cdp_api_action_provider(cdp_provider_config)

# After (0.6.0)
cdp_api_action_provider()  # No arguments
```

### Removed Functions
The following functions were completely removed in 0.6.0:
- `CdpWalletActionProvider_deploy_contract`
- `CdpWalletActionProvider_deploy_nft`
- `CdpWalletActionProvider_deploy_token`
- `CdpWalletActionProvider_trade`

## 4. Wallet Structure Changes & Compatibility Issues

### The Problem

AgentKit 0.6.0 changed how wallet data is stored and validated. Agents created with 0.4.0 had wallet addresses stored in a format that became **invalid** in 0.6.0, causing this error:

```
ApiError(http_code=404, error_type=not_found, error_message=EVM account with given address not found.)
```

### Wallet Data Structure Differences

**AgentKit 0.4.0 Format:**
```json
{
  "default_address_id": "0x1234...",
  "wallet_secret": "encrypted_data",
  "account_data": { ... }
}
```

**AgentKit 0.6.0 Format:**
```json
{
  "default_address_id": "0x5678...",
  "wallet_secret": "new_encrypted_format",
  "provider_specific_data": { ... }
}
```

The address validation and wallet initialization process changed, making old wallet addresses incompatible.

### Two Wallet Management Approaches Found

1. **Older agents**: `cdp_wallet_address: null` → Create wallets **on-demand** → ✅ **Work with 0.6.0**
2. **Newer agents**: Pre-stored `cdp_wallet_address` → Use **stored addresses** → ❌ **Fail with 0.6.0**

## 5. Wallet Fix Script

### What the Script Does

We created `scripts/fix_invalid_wallets.py` to resolve wallet compatibility issues:

1. **Scans all agents** with stored wallet addresses
2. **Tests each address** by attempting to initialize it with the new AgentKit 0.6.0 API
3. **Identifies invalid addresses** that cause "not found" errors
4. **Clears invalid wallet data** so agents can create fresh, compatible wallets

### How It Works

```python
# Test if wallet address exists in CDP 0.6.0
wallet_config = CdpEvmServerWalletProviderConfig(
    api_key_id=config.cdp_api_key_name,
    api_key_secret=config.cdp_api_key_private_key,
    network_id="base-mainnet",
    address=wallet_address,
    wallet_secret=None
)

# This will throw an error if address is invalid
wallet_provider = CdpEvmServerWalletProvider(wallet_config)
```

### Usage

```bash
# Check what would be fixed (dry run)
python scripts/fix_invalid_wallets.py --dry-run

# Fix all invalid wallets
python scripts/fix_invalid_wallets.py

# Fix specific agent
python scripts/fix_invalid_wallets.py --agent-id agent_id_here
```

### Results

In our case, **all 5 agents** with wallet addresses had invalid addresses and were successfully fixed:

```
Found invalid wallet: d1c0kqo9i6t8calft7l0 -> 0x0B272145aA2c52587263a09a03eAcc78568082Bd
Found invalid wallet: comp1 -> 0x2cce7994C30BB178AC4D98149067245b8104fA72
[... 3 more agents ...]

Summary: 5 invalid addresses found, 5 fixed
```

## 6. Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Updated dependency versions |
| `example.env` | Added new CDP environment variables |
| `intentkit/clients/cdp.py` | Replaced wallet provider classes, added env var fallbacks |
| `intentkit/skills/cdp/__init__.py` | Updated imports, removed deprecated references |
| `intentkit/skills/cdp/schema.json` | Removed deprecated function definitions |
| `scripts/fix_invalid_wallets.py` | **New script** to fix wallet compatibility |

## 7. Migration Steps

1. **Update dependencies:** `uv sync`
2. **Update environment variables** (see section 2)
3. **Fix wallet compatibility:** `python scripts/fix_invalid_wallets.py`
4. **Test the server:** `uvicorn app.api:app --reload`
5. **Verify wallet functions work**

## 8. Post-Upgrade Behavior

### Before Fix
- ❌ Agents with stored wallet addresses throw "EVM account not found" errors
- ❌ Wallet functions completely broken
- ❌ Server startup issues with CDP initialization

### After Fix
- ✅ All agents work without wallet-related errors
- ✅ Agents create fresh, compatible wallets on-demand
- ✅ Existing funded wallets are re-discovered and maintained
- ✅ New agents work seamlessly with 0.6.0

## 9. Key Insights & Future Considerations

1. **On-demand wallet creation** is more resilient than pre-stored addresses
2. **Wallet data format changes** between AgentKit versions can break compatibility
3. **The fix script approach** allows gradual migration without data loss
4. **Monitor for similar issues** in future AgentKit upgrades
5. **Document wallet changes** in release notes