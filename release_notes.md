## New Features

- **Agent Middleware Support**: Agents now support LangChain middleware including Todo List for task planning, automatic LLM Tool Selector when agents have more than 10 skills, Context Editing for efficient context management, and built-in Tool Retry and Model Retry for improved reliability.
- **New Agent Settings**: Added Internet Search, Super Mode, and Todo List toggles to the agent configuration UI with proper labels and descriptions.

## Improvements

- Refactored web search and super mode internals for cleaner architecture.
- Upgraded frontend to Node.js 24 and added a dedicated development Dockerfile for better hot reload support in Docker Compose.
- Fixed frontend rendering issues with checkbox fields.
- Updated dependencies.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.11.19...v0.11.20
