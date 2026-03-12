# v0.11.26

## New Features

- **Agent Slug Identifiers**: Agents can now be identified by human-readable slugs in addition to their IDs, making agent URLs and references more user-friendly.
- **New AI Models**: Added Hunter Alpha and Healer Alpha models from OpenRouter, expanding the available model selection.

## Improvements

- Improved system prompt generation for better agent behavior.
- Refactored internal engine architecture for clearer naming and better maintainability.
- Fixed a cache invalidation bug where changes to agent data (such as wallet addresses, API keys, or credentials) were not properly triggering agent reloads.
- Removed legacy skill pattern mechanism to simplify the codebase.
- Updated dependencies.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.11.25...v0.11.26
