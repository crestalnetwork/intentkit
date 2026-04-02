# Release v0.17.7

## New Features

### Account Linking & Plan Initialization
- Users can now link Google and EVM wallet accounts to their profile, with a dedicated account management page showing linked providers.
- Team plans are automatically initialized when creating a team: Google users receive a Free plan, and EVM wallet users with a portfolio value over $20 also receive a Free plan.
- Linking a Google account upgrades the user's first team from None to Free plan.
- Google accounts cannot be unlinked once linked. EVM wallets can only be unlinked if a Google account is already linked.

### Pricing Plan Tiers
- Added four pricing plan tiers (None, Free, Pro, Max) with configurable quotas, refill rates, and monthly credit issuance for paid plans.

### Team-Based Billing
- Migrated billing system from user-based to team-based, aligning credit accounts and plan management with team ownership.

## Improvements
- Improved documentation with PyPI badge and security features in README.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.6...v0.17.7
