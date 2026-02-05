# Release v0.9.31

## Improvement

- **Transfer Script**: Optimized `scripts/transfer_cdp_agent_wallets.py` to:
  - Automatically resolve invalid owner addresses by stripping whitespace and adding `0x` prefixes.
  - Lower `DEFAULT_GAS_RESERVE_ETH` to `0.00001` to allow transfers regarding small balances.
  - Suppress logs for zero-balance wallets to reduce noise.
  - Improve error logging to explicitly state why a transfer is skipped (e.g., `skip:owner_not_found`, `skip:owner_address_invalid`).
  - Added transaction summary report at the end of execution.

- **CDP Wallet**: Exposed `close_cdp_client` method in `intentkit/wallets/cdp.py` for better resource management.

## New Features

- **Diagnostic Tool**: Added `scripts/list_agent_assets.py` to list agent assets and wallet addresses for verification.

Full Changelog: [v0.9.30...v0.9.31](https://github.com/crestalnetwork/intentkit/compare/v0.9.30...v0.9.31)