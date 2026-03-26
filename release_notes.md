## New Features

- **WeChat Integration**: Full WeChat bot support via iLink Bot API, with rich media messaging and SSE streaming.
- **Telegram Rich Media**: Enhanced Telegram bot with image, video, and audio message support via SSE streaming.
- **Team Lead API**: New team lead endpoints for managing agents, channels, and chat through the team API.
- **DeFi Protocol Skills**: Added Aave V3 (lending/borrowing), Uniswap V3 (DEX trading), Aerodrome Slipstream (DEX), and Polymarket (prediction markets) skill categories.
- **OpenSea NFT Skills**: Buy, sell, list, and manage NFTs on OpenSea marketplace.
- **Remote MCP Server Support**: Wrap remote MCP servers as IntentKit skill categories.
- **Per-Skill Availability Check**: Skills can now declare availability based on multi-provider configuration.
- **Lead Agent Improvements**: Auto-generate avatars for lead-created agents, require slug and purpose fields, dynamic LLM model selection.

## Improvements

- Improved LLM model picker with dynamic OpenAI-compatible provider fallbacks.
- Activities and Posts tabs now conditionally display based on agent configuration.
- Standardized error handling across 16 skill categories.
- Restructured documentation and updated deployment configurations.

## Bug Fixes

- Fixed various type errors across the codebase.
- Fixed tab visibility logic and UI improvements in the frontend.
- Fixed lead cache invalidation and context propagation issues.
- Resolved frontend dependency security alerts.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.15.0...v0.16.0
