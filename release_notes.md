# Release v0.17.37

## New Features

- **Skill Validation for Agent Creation**: The agent manager now validates skill configurations when creating new agents, ensuring only valid skills can be assigned. Invalid skill names or formats are rejected with clear error messages.
- **Enhanced Skill Listing**: The available skills listing now shows individual skill names and descriptions under each category, making it easier for the agent manager to select the right skills.
- **Improved Agent Manager Prompt**: The agent manager now includes a detailed skill configuration format with concrete examples, guiding it to always check available skills before configuring an agent.

## Improvements

- Unified lead agent endpoints for all channel types (Telegram, WeChat, etc.)
- Stale skills (removed from codebase) are now automatically cleaned up when agents are updated

## Bug Fixes

- Fixed Telegram lead agent verification code and auto-bind
- Fixed skill message attachments not dispatching correctly to WeChat and Telegram

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.36...v0.17.37
