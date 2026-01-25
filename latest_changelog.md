## v0.9.3

### Bug Fixes
- Fixed a critical security bypass in `transfer_erc20_gasless` where omitting the `privy_wallet_address` would cause the transfer to fall back to a direct owner transfer, bypassing the Allowance Module limits.
- Added `get_wallet` method to `PrivyClient` to fetch wallet details by ID.
- Automatically fetch wallet address in `transfer_erc20_gasless` if not provided, ensuring the secure Allowance Module path is always attempted first when enabled.

[Diff v0.9.2...v0.9.3](https://github.com/crestalnetwork/intentkit/compare/v0.9.2...v0.9.3)