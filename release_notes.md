# Release v0.17.44

## Bug Fixes

- Fixed OpenRouter-based image generation for both auto-generated agent/team avatars and image skills — generation now succeeds reliably.

## Improvements

- Migrated the OpenRouter integration to the official OpenRouter Python SDK for better retry handling and type safety.
- Traffic going through OpenRouter is now attributed to IntentKit in the OpenRouter dashboard (previously attributed to LangChain).
- Added cost reconciliation logging so OpenRouter-reported costs can be compared against internal token-based billing.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.43...v0.17.44
