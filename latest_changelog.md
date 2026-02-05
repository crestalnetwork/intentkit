## v0.9.30

### Bug Fixes

- **CDP Wallet Transfer**: Fixed a crash in `scripts/transfer_cdp_agent_wallets.py` caused by insufficient ETH balance/gas. The script now gracefully skips such agents.

### Improvements

- **Logging**: Added summary logging to the CDP transfer script to show total agents processed and skipped.
- **Logging**: Refined log levels to reduce noise; skipped transfers are now logged at DEBUG level.

[Full Changelog](https://github.com/crestalnetwork/intentkit/compare/v0.9.29...v0.9.30)