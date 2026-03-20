## New Features

- **Team Lead Chat**: A new "Lead" tab in the frontend lets you chat directly with a team lead agent that manages all your agents. Create, configure, update, and monitor agents through natural conversation.
- **Team Channel Integration**: Added Telegram team channel integration for team-level communication.
- **Image Skills**: New image skill category with multi-provider support for image generation and processing.
- **Image Attachments in Chat**: Chat messages now render image attachments with lightbox preview and download support.
- **Custom LLM Providers**: Added support for configuring custom LLM providers.
- **Team Management**: New team management features with invite system and Redis-based caching.

## Improvements

- Reorganized skill system for better maintainability — cleaned up unused skills and consolidated categories.
- Simplified LLM model configuration by removing legacy fields.
- Improved agent executor architecture with extracted helpers and reduced complexity.
- Enhanced data integrity with fixes for quota race conditions and credit handling.
- Various stability improvements including cache eviction, timeouts, and resource management.

## Bug Fixes

- Fixed issues in the security module.
- Fixed chat cancellation handling to cleanly remove dangling messages.
- Fixed search pricing calculation.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.12.3...v0.13.0
