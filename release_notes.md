# Release v0.17.48

## New Features

- **WeChat image support**: Agents can now receive and process images sent by users through WeChat. Images are extracted from incoming messages and passed to the agent's model for understanding.

## Improvements

- Improved error handling when users send images to agents using models that don't support image input — a clear message is now returned instead of a silent failure.
- Simplified image capability detection for agents by removing the deprecated image parser skill fallback.
- Optimized agent delegation to avoid unnecessary database queries when forwarding attachments between agents.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.47...v0.17.48
