# Release v0.17.41

## Bug Fixes

- Fixed a bug where sub-agent calls (via `call_agent`) reused the same conversation thread across invocations, causing stale message history to interfere with new skill configurations. Sub-agent calls are now stateless — each call gets a fresh conversation context.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.40...v0.17.41
