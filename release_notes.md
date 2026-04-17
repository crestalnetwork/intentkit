# Release v0.17.52

## New Features

- **Alert forwarding for Go integrations**: The Telegram and WeChat integration services now automatically forward error-level events to the configured alert channel (Telegram or Slack), matching the behavior already in place on the Python side. Both stacks share the same per-minute alert budget so operators are not flooded.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.51...v0.17.52
