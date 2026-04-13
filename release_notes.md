# Release v0.17.35

## Bug Fixes

- Fixed an issue where the lead agent could not delegate tasks to team agents via WeChat and Telegram channels. The agent routing was using an incorrect identifier, causing sub-agent calls to always fail from these channels.
- Added a safety mechanism to prevent Gemini 3 model calls from failing with "empty parts" errors due to corrupted conversation history.

## Improvements

- Public agent sync now uses slug-based matching for more reliable updates, and supports tags and archive status.
- Cleaned up Team API endpoint organization for better consistency.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.34...v0.17.35
