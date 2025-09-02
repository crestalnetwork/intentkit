## v0.6.25

### Refactoring
- Simplified Dockerfile dependency installation process
- Removed unnecessary await from sync get_system_config calls in Twitter module

### Build & Configuration
- Updated project name and added workspace configuration

### Documentation
- Updated changelog for v0.6.23 release

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.23...v0.6.25

## v0.6.23

### Features
- Add reasoning_effort parameter for gpt-5 models

### Documentation
- Update changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.22...v0.6.23

## v0.6.22

### Features
- **XMTP Skills Enhancement**: Expanded XMTP skills to support multiple networks, improving cross-chain communication capabilities
- **DexScreener Integration**: Added comprehensive DexScreener skills for enhanced token and pair information retrieval
  - New `get_pair_info` skill for detailed trading pair data
  - New `get_token_pairs` skill for token pair discovery
  - New `get_tokens_info` skill for comprehensive token information
  - Enhanced search functionality with improved utilities

### Technical Improvements
- Added new Web3 client utilities for better blockchain interaction
- Enhanced chat functionality in core system
- Updated agent schema with improved configuration options
- Improved skill base classes with better error handling

### Dependencies
- Updated project dependencies for better compatibility and security

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.21...v0.6.22

## v0.6.21

### Features
- Added agent onchain fields support
- Added web3 client and updated skill base class
- Added clean thread memory functionality

### Improvements
- Package upgrade and maintenance

### Bug Fixes
- Fixed typo in intentkit package info

### Documentation
- Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.20...v0.6.21

## v0.6.20

### Features
- **Firecrawl Integration**: Enhanced firecrawl scraping capabilities by consolidating logic into a single `firecrawl_scrape` skill, removing the redundant `firecrawl_replace_scrape` skill
- **Web3 Client**: Added web3 client support to skills for better blockchain integration
- **XMTP Transfer**: Improved XMTP transfer validation and checking mechanisms

### Bug Fixes
- Fixed Supabase integration bugs
- Better XMTP transfer validation and error handling
- Removed deprecated skill context to improve performance

### Documentation
- Updated Firecrawl skill documentation
- Enhanced changelog maintenance

### Technical Improvements
- Code quality improvements and lint fixes
- Minor performance optimizations

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.19...v0.6.20

## v0.6.19

### Features
- **Credit System**: Add base credit type amount fields and migration script
- **Credit Events**: Enhance consistency checker and add fixer script
- **Event System**: Add event check functionality
- **Transaction Details**: Add fee detail in event and tx

### Bug Fixes
- **CDP Networks**: Add network id mapping hack for cdp mainnet networks
- **UI**: Always hide skill details
- **Onchain Options**: Better onchain options description

### Technical Improvements
- Enhanced credit event consistency checking and fixing capabilities
- Improved network compatibility for CDP mainnet operations
- Better transaction fee tracking and reporting

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.18...v0.6.19

## v0.6.18

### New Features
- **Casino Skills**: Added comprehensive gambling and gaming skill set for interactive agent entertainment
    - **Deck Shuffling**: Multi-deck support with customizable jokers for Blackjack and card games
    - **Card Drawing**: Visual card display with PNG/SVG images for interactive gameplay
    - **Quantum Dice Rolling**: True quantum randomness using QRandom API for authentic dice games
    - **State Management**: Persistent game sessions with deck tracking and rate limiting
    - **Gaming APIs**: Integration with Deck of Cards API and QRandom quantum random number generator

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.17...v0.6.18

## v0.6.17

### ✨ New Features
- **Error Tracking**: Add error_type field to chat message model for better error tracking

### 🔧 Improvements
- **Core Engine**: Refactor core engine and update models for better performance
- **System Messages**: Refactor system messages handling
- **Error Handling**: Refactor error handling system

### 🐛 Bug Fixes
- **Wallet Provider**: Fix wallet provider JSON configuration
- **Linting**: Fix linting issues

### 📚 Documentation
- Update changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.16...v0.6.17

## v0.6.16

### 🐛 Bug Fixes
- **Agent Generator**: Fixed missing wallet_provider default configuration in agent schema generation
- **Schema Updates**: Updated agent schema JSON to reflect latest configuration requirements

### 🔧 Improvements
- Enhanced agent generator to include CDP wallet provider as default
- Improved agent configuration consistency

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.15...v0.6.16

## v0.6.15

### 🔧 Improvements
- **Validation Logging**: Enhanced error logging in schema validation for better debugging
- **Documentation**: Updated changelog with v0.6.14 release notes

### 🐛 Bug Fixes
- Improved error handling and logging in generator validation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.14...v0.6.15

## v0.6.14

### 🐛 Bug Fixes
- **Readonly Wallet Address**: Fixed readonly_wallet_address issue

### 🔧 Changes
- Fixed readonly wallet address handling

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.13...v0.6.14

## v0.6.13

### ✨ New Features
- **Readonly Wallet Support**: Added readonly wallet provider and functionality
- **Agent API Streaming**: Implemented SSE (Server-Sent Events) for chat stream mode in agent API
- **Internal Stream Client**: Added internal streaming client capabilities
- **Entrypoint System Prompts**: Added system prompt support for entrypoints, including XMTP entrypoint prompts
- **Agent Model Configuration**: Updated agent model configuration system

### 🔧 Improvements
- **Documentation**: Updated changelog and LLM documentation
- **Twitter Entrypoint**: Removed deprecated Twitter entrypoint

### 🐛 Bug Fixes
- **Agent Context Type**: Fixed agent context type issues
- **Error Messages**: Improved error message handling

### Diff
[Compare v0.6.12...v0.6.13](https://github.com/crestalnetwork/intentkit/compare/v0.6.12...v0.6.13)

## v0.6.12

### 🔧 Improvements
- **Skill Messages**: Consolidated artifact attachments into skill messages for better organization
- **Documentation**: Updated changelog entries

### Diff
[Compare v0.6.11...v0.6.12](https://github.com/crestalnetwork/intentkit/compare/v0.6.11...v0.6.12)

## v0.6.11

### ✨ New Features
- **XMTP Integration**: Added new XMTP features including swap and price skills
- **User Wallet Info**: Enhanced user wallet information display
- **DeepSeek Integration**: Updated DeepSeek integration with improved functionality

### 🐛 Bug Fixes
- **Search Functionality**: Temporarily disabled search for GPT-5 to resolve issues
- **Configuration**: Better handling of integer config loading and number type validation
- **Fee Agent Account**: Fixed fee_agent_account assignment in expense_summarize function
- **Security**: Fixed clear-text logging of sensitive information (CodeQL alerts #31, #32)
- **XMTP Schema**: Added missing XMTP schema files
- **DeepSeek Bug**: Resolved DeepSeek-related bugs

### 🔧 Improvements
- **Prompt System**: Refactored prompt system for better performance
- **Code Quality**: Improved formatting and code organization
- **Build Configuration**: Updated GitHub workflow build configuration
- **Dependencies**: Updated uv sync and dependency management

### 📚 Documentation
- Updated changelog entries throughout development cycle
- Enhanced documentation for new features

### Diff
[Compare v0.6.10...v0.6.11](https://github.com/crestalnetwork/intentkit/compare/v0.6.10...v0.6.11)

## v0.6.10

### ✨ New Features
- **XMTP Integration**: Added new XMTP message transfer skill with attachment support
- **LangGraph 6.0 Upgrade**: Updated to LangGraph 6.0 for improved agent capabilities

### 🔧 Improvements
- **API Key Management**: Standardized API key retrieval across all skills for better consistency
- **Skill Context**: Refactored skill context handling for improved performance and maintainability
- **Skill Architecture**: Enhanced base skill classes with better API key management patterns
- **XMTP Skill**: Updated XMTP skill image format and schema configuration
- **Dependencies**: Added jsonref dependency for JSON reference handling
- **Build Workflow**: Updated GitHub Actions build workflow configuration

### 🐛 Bug Fixes
- **XMTP Skill**: Align state typing and schema enum/titles for public/private options
- **GPT-5 Features**: Fixed GPT-5 model features and capabilities implementation
- **CI Improvements**: Fixed continuous integration workflow issues
- **Agent & LLM Model Validation**: Enhanced agent and LLM models with improved validation capabilities and error handling

### 🛠️ Technical Changes
- Updated 169 files with comprehensive refactoring
- Added XMTP skill category with transfer capabilities
- Improved skill base classes across all categories
- Enhanced context handling in core engine and nodes
- Updated dependencies and lock files
- Enhanced XMTP skill metadata and configuration files
- Updated skill image format for better compatibility
- Updated `intentkit/pyproject.toml` with jsonref dependency
- Enhanced `.github/workflows/build.yml` configuration
- Updated `intentkit/uv.lock` with new dependency

### 📚 Documentation
- **Changelog**: Updated changelog documentation with comprehensive release notes

### Diff
[Compare v0.6.9...v0.6.10](https://github.com/crestalnetwork/intentkit/compare/v0.6.9...v0.6.10)

## v0.6.9

### 📚 Documentation
- **API Documentation**: Updated API documentation URLs to use localhost for development

### 🔧 Maintenance  
- **Sentry Configuration**: Updated sentry configuration settings

### Diff
[Compare v0.6.8...v0.6.9](https://github.com/crestalnetwork/intentkit/compare/v0.6.8...v0.6.9)

## v0.6.8

### 🚀 Features & Improvements

#### 🔧 Dependency Updates
- **LangGraph SDK & LangMem**: Updated to latest versions for improved performance
- **FastAPI**: Updated core dependencies for better stability

#### 📚 Documentation
- **LLM Integration Guide**: Enhanced guide with better examples and updated instructions
- **Cursor Rules**: Converted to symlink for better maintainability

#### 💾 Database
- **Connection Pooling**: Enhanced database connection pooling configuration with new parameters for better performance and resource management

### 🐛 Bug Fixes
- **Twitter**: Fixed rate limit handling for improved reliability

### 🔧 Maintenance
- **Elfa**: Migrated to v2 API for better functionality
- **Documentation**: Various changelog and documentation updates

### Diff
[Compare v0.6.7...v0.6.8](https://github.com/crestalnetwork/intentkit/compare/v0.6.7...v0.6.8)

## v0.6.7

### 🚀 Features
- **Autonomous Task Management System**: Added comprehensive autonomous task management capabilities with new skills for creating, updating, and managing autonomous tasks
- **Agent Information Endpoint**: New endpoint to retrieve current agent information including EVM and Solana wallet addresses
- **Enhanced Agent Model**: Added EVM and Solana wallet address fields to AgentResponse model
- **Configurable Payment Settings**: Added configurable free_quota and refill_amount to payment settings

### 🔧 Improvements
- **Simplified Autonomous Tasks**: Removed enabled parameter from add_autonomous_task skill - tasks are now always enabled by default
- **Better Task Integration**: Autonomous task information is now included in entrypoint rules system prompt
- **Code Organization**: Refactored quota reset functions to AgentQuota class and moved update_agent_action_cost function to agent module

### 🐛 Bug Fixes
- Fixed autonomous skill bugs and ensured proper serialization of autonomous tasks in agent operations
- Improved code formatting and removed unused files

### 📚 Documentation
- Updated changelog with comprehensive release notes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.6...v0.6.7

## v0.6.6

### 🚀 Features
- **Twitter Timeline Enhancement**: Exclude replies from twitter timeline by default to improve content quality and relevance

### 🔧 Technical Details
- Modified twitter timeline skill to filter out reply tweets by default
- This change improves the signal-to-noise ratio when fetching timeline data

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5...v0.6.6

## v0.6.5

### 🚀 Features
- Add sanitize_privacy method to ChatMessage model for better privacy handling
- Add redis_db parameter to all redis connections for improved database management

### 🔧 Improvements
- Prevent twitter reply skill from replying to own tweets to avoid self-loops
- Better agent API documentation with improved clarity and examples
- Enhanced agent documentation with clearer explanations

### 🐛 Bug Fixes
- Fix agent data types for better type safety
- Fix bug in agent schema validation
- Remove number field in agent model to simplify structure
- Use separate connection for langgraph migration setup to prevent conflicts
- Fix typo in documentation

### 📚 Documentation
- Improved agent API documentation
- Updated changelog entries
- Better agent documentation structure

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.4...v0.6.5

## v0.6.4

### 🔧 Maintenance
- **Dependency Management**: Rollback langgraph-checkpoint-postgres version for stability
- **Package Updates**: Update dependencies in pyproject.toml
- **Documentation**: Documentation improvements

### 🐛 Bug Fixes
- **Compatibility**: Fixed dependency compatibility issues

### 🚀 Improvements
- **Stability**: Enhanced system stability with dependency rollbacks

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.3...v0.6.4

## v0.6.3

### 🚀 Features
- **CDP Swap Skill**: Added CDP swap skill for token swapping functionality

### 🐛 Bug Fixes
- Fixed lint error
- Fixed a type error

### 🔧 Maintenance
- Updated dependencies in pyproject.toml
- Fixed dependency error
- Updated package versions
- Documentation changelog updates

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.2...v0.6.3

## v0.6.2

### 🚀 Features
- **Agent API Enhancement**: Added comprehensive agent API sub-application with CORS support and improved error handling
- **Authentication Improvements**: Implemented token-based authentication for agent API endpoints
- **Credit Tracking**: Enhanced credit event tracking with agent_wallet_address field for better monitoring
- **Chat API Flexibility**: Made user_id optional in chat API with automatic fallback to agent.owner
- **Documentation Updates**: Restructured and updated API documentation for better clarity

### 🔧 Improvements
- **Twitter Service**: Refactored twitter service for better maintainability
- **Text Processing**: Improved formatting in extract_text_and_images function
- **Agent Authentication**: Streamlined agent and admin authentication systems
- **Supabase Integration**: Fixed supabase link issues
- **API Key Skills**: Enhanced description for get API key skills

### 📚 Documentation
- Updated README with latest information
- Restructured API documentation files
- Added comprehensive agent API documentation

### 🛠️ Technical Changes
- Updated dependencies with uv sync
- Various code refactoring for better code quality
- Fixed typos in chat message handling

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.1...v0.6.2

## v0.6.1

### Features
- feat: add public key to supabase

### Bug Fixes
- fix: node log level
- fix: cdp get balance bug
- fix: close some default skills

### Documentation
- doc: changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0...v0.6.1

## v0.6.0

### 🚀 Features
- **IntentKit Package Publishing**: The intentkit package is now published and available for installation
- **Web Scraper Skills**: Added comprehensive web scraping capabilities to scrape entire sites in one prompt
- **Firecrawl Integration**: New Firecrawl skill for advanced web content extraction
- **Supabase Skills**: Complete Supabase integration with data operations and error handling
- **HTTP Skills**: Generic HTTP request capabilities for external API interactions
- **Enhanced Skill Context**: More contextual information available to skills during execution

### 🔧 Improvements
- **Core Refactoring**: Major refactoring of the intentkit core system for better performance
- **Stream Executor**: Improved streaming capabilities for real-time responses
- **Agent Creation**: Streamlined agent creation process
- **Memory Management**: Better memory handling with SQLite support for testing
- **CDP Wallet Integration**: Enhanced CDP wallet functionality with automatic wallet creation
- **Skill Schema Updates**: Improved skill schemas with conditional validation
- **LangGraph Integration**: Better PostgreSQL saver initialization for LangGraph

### 🐛 Bug Fixes
- Fixed import issues in core modules
- Corrected skills path and added webp support in admin schema
- Fixed CDP balance retrieval functionality
- Resolved wallet creation issues during agent initialization
- Various lint and formatting fixes

### 📚 Documentation
- Updated LLM integration guide
- Enhanced skill development documentation
- Improved changelog maintenance

### Breaking Changes
- Core intentkit package structure has been refactored
- Some skill interfaces may have changed due to enhanced context support

### Migration Guide
- Update your intentkit package installation to use the new published version
- Review skill implementations if using custom skills
- Check agent creation code for any compatibility issues

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.5.9...v0.6.0

## v0.5.0

### Breaking Changes
- Switch to uv as package manager

## v0.4.0

### New Features
- Support Payment

## 2025-02-26

### New Features
- Chat entity and API

## 2025-02-25

### New Features
- Elfa integration

## 2025-02-24

### New Features
- Add input token limit to config
- Auto clean memory after agent update

## 2025-02-23

### New Features
- Defillama skills

## 2025-02-21

### New Features
- AgentKit upgrade to new package

## 2025-02-20

### New Features
- Add new skill config model
- Introduce json schema for skill config

## 2025-02-18

### New Features
- Introduce json schema for agent model
- Chain provider abstraction and quicknode

## 2025-02-17

### New Features
- Check and get the telegram bot info when creating an agent

## 2025-02-16

### New Features
- Chat History API
- Introduce to Chat ID concept

## 2025-02-15

### New Features
- GOAT Integration
- CrossMint Wallet Integration

## 2025-02-14

### New Features
- Auto create cdp wallet when create agent
- CryptoCompare skills

## 2025-02-13

### New Features
- All chats will be saved in the db table chat_messages

### Breaking Changes
- Remove config.debug_resp flag, you can only use debug endpoint for debugging
- Remove config.autonomous_memory_public, the autonomous task will always use chat id "autonomous"

## 2025-02-11

### Improvements
- Twitter account link support redirect after authorization

## 2025-02-05

### New Features
- Acolyt integration

## 2025-02-04

### Improvements
- split scheduler to new service
- split singleton to new service

## 2025-02-03

### Breaking Changes
- Use async everywhere

## 2025-02-02

### Bug Fixes
- Fix bugs in twitter account binding

## 2025-02-01

### New Features
- Readonly API for better performance

## 2025-01-30

### New Features
- LLM creativity in agent config
- Agent memory cleanup by token count

## 2025-01-28

### New Features
- Enso tx CDP wallet broadcast

## 2025-01-27

### New Features
- Sentry Error Tracking

### Improvements
- Better short memory management, base on token count now
- Better logs

## 2025-01-26

### Improvements
- If you open the jwt verify of admin api, it now ignore the reqest come from internal network
- Improve the docker compose tutorial, comment the twitter and tg entrypoint service by default

### Break Changes
- The new docker-compose.yml change the service name, add "intent-" prefix to all services

## 2025-01-25

### New Features
- DeepSeek LLM Support!
- Enso skills now use CDP wallet
- Add an API for frontend to link twitter account to an agent

## 2025-01-24

### Improvements
- Refactor telegram services
- Save telegram user info to db when it linked to an agent

### Bug Fixes
- Fix bug when twitter token refresh some skills will not work

## 2025-01-23

### Features
- Chat API released, you can use it to support a web UI

### Improvements
- Admin API: 
  - When create agent, id is not required now, we will generate a random id if not provided
  - All agent response data is improved, it has more data now
- ENSO Skills improved

## 2025-01-22

### Features
- If admin api enable the JWT authentication, the agent can only updated by its owner
- Add upstream_id to Agent, when other service call admin API, can use this field to keep idempotent, or track the agent

## 2025-01-21

### Features
- Enso add network skill

### Improvements
- Enso skills behavior improved

## 2025-01-20

### Features
- Twitter skills now get more context, agent can know the author of the tweet, the thread of the tweet, and more.

## 2025-01-19

### Improvements
- Twitter skills will not reply to your own tweets
- Twitter docs improved

## 2025-01-18

### Improvements
- Twitter rate limit only affected when using OAuth
- Better twitter rate limit numbers
- Slack notify improved

## 2025-01-17

### New Features
- Add twitter skill rate limit

### Improvements
- Better doc/create_agent.sh
- OAuth 2.0 refresh token failure handling

### Bug Fixes
- Fix bug in twitter search skill

## 2025-01-16

### New Features
- Twitter Follow User
- Twitter Like Tweet
- Twitter Retweet
- Twitter Search Tweets

## 2025-01-15

### New Features
- Twitter OAuth 2.0 Authorization Code Flow with PKCE
- Twitter access token auto refresh
- AgentData table and AgentStore interface

## 2025-01-14

### New Features
- ENSO Skills

## 2025-01-12

### Improvements
- Better architecture doc: [Architecture](docs/architecture.md)

## 2025-01-09

### New Features
- Add IntentKitSkill abstract class, for now, it has a skill store interface out of the box
- Use skill store in Twitter skills, fetch skills will store the last processed tweet ID, prevent duplicate processing
- CDP Skills Filter in Agent, choose the skills you want only, the less skills, the better performance

### Improvements
- Add a document for skill contributors: [How to add a new skill](docs/contributing/skills.md)

## 2025-01-08

### New Features
- Add `prompt_append` to Agent, it will be appended to the entire prompt as system role, it has stronger priority
- When you use web debug mode, you can see the entire prompt sent to the AI model
- You can use new query param `thread` to debug any conversation thread

## 2025-01-07

### New Features
- Memory Management

### Improvements
- Refactor the core ai agent creation

### Bug Fixes
- Fix bug that resp debug model is not correct

## 2025-01-06

### New Features
- Optional JWT Authentication for admin API

### Improvements
- Refactor the core ai agent engine for better architecture
- Telegram entrypoint greeting message

### Bug Fixes
- Fix bug that agent config update not taking effect sometimes

## 2025-01-05

### Improvements
- Telegram entrypoint support regenerate token
- Telegram entrypoint robust error handling

## 2025-01-03

### Improvements
- Telegram entrypoint support dynamic enable and disable
- Better conversation behavior about the wallet

## 2025-01-02

### New Features
- System Prompt, It will affect all agents in a deployment.
- Nation number in Agent model

### Improvements
- Share agent memory between all public entrypoints
- Auto timestamp in db model

### Bug Fixes
- Fix bug in db create from scratch

## 2025-01-01

### Bug Fixes
- Fix Telegram group bug

## 2024-12-31

### New Features
- Telegram Entrypoint

## 2024-12-30

### Improvements
- Twitter Integration Enchancement

## 2024-12-28

### New Features
- Twitter Entrypoint
- Admin cron for quota clear
- Admin API get all agents

### Improvements
- Change lint tools to ruff
- Improve CI
- Improve twitter skills

### Bug Fixes
- Fix bug in db base code

## 2024-12-27

### New Features
- Twitter Skills
    - Get Mentions
    - Get Timeline
    - Post Tweet
    - Reply Tweet

### Improvements
- CI/CD refactoring for better security

## 2024-12-26

### Improvements
- Change default plan to "self-hosted" from "free", new agent now has 9999 message limit for testing
- Add a flag "DEBUG_RESP", when set to true, the Agent will respond with thought processes and time costs
- Better DB session management

## 2024-12-25

### Improvements
- Use Poetry as package manager
- Docker Compose tutorial in readme

## 2024-12-24

### New Features
- Multiple Agent Support
- Autonomous Agent Management
- Blockchain Integration (CDP for now, will add more)
- Extensible Skill System
- Extensible Plugin System

### Improvements
- Change lint tools to ruff
- Improve CI
- Improve twitter skills

### Bug Fixes
- Fix bug in db base code