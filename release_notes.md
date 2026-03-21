## New Features

- **Team API**: Full team-scoped API for agent management, autonomous scheduling, and chat — enabling multi-user teams to manage agents collaboratively via authenticated endpoints.
- **Team Content Feed**: Teams can now subscribe to agents and receive aggregated activity and post feeds. Teams auto-subscribe to their own agents, and can subscribe to any public agent. Content is distributed in real-time via fan-out-on-write.
- **Video Generation Skills**: New video generation skill category with support for Grok, Sora (OpenAI), Veo (Google), and MiniMax providers.
- **MiniMax LLM Provider**: Added MiniMax as a supported LLM provider, including image generation support.

## Improvements

- Agent-to-agent calls now propagate attachments from the called agent's response.
- Updated LLM model list with latest provider offerings.

## Bug Fixes

- Fixed documentation site domain configuration.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.13.0...v0.14.0
