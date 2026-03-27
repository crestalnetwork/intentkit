## New Features

- **Morpho Blue Skills**: Added full Morpho Blue lending protocol support — supply collateral, withdraw collateral, borrow, repay, and query market positions directly on Morpho Blue markets.
- **MetaMorpho Vault Query**: New vault data skill to check MetaMorpho Vault info including total assets, share price, and underlying token.
- **Agent UI Enhancements**: Agent cards now display description/purpose fallback text, skill & capability tags, and slug identifiers for easier navigation.
- **Image Upload**: Added image upload support for team and agent profile pictures.
- **WeChat Debug Logging**: Added DEBUG log level support and diagnostic logging for WeChat integration.

## Improvements

- Payment-related scheduler jobs are now gated behind the payment_enabled configuration flag.
- Removed auto-creation of example agent on startup for cleaner initial setup.

## Bug Fixes

- Fixed an issue with fractional token triggers in the Summarization middleware.
- Fixed API proxy path handling in frontend deployments.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.16.1...v0.16.2
