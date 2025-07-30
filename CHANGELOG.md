# Changelog

## v0.6.8-dev2

### Changes
- **chore**: update fastapi and dependencies
- **chore**: convert .cursorrules to symlink to LLM.md
- **docs**: update llm integration guide
- **docs**: update changelog and llm guide

### Diff
[Compare v0.6.8-dev1...v0.6.8-dev2](https://github.com/crestalnetwork/intentkit/compare/v0.6.8-dev1...v0.6.8-dev2)

## v0.6.7-dev9

### 🔧 Improvements

- **Database Connection Pooling**: Enhanced database connection pooling configuration with new parameters for better performance and resource management

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev8...v0.6.7-dev9

## v0.6.7-dev8

### 🐛 Bug Fixes
- **Twitter**: Fixed rate limit handling

### 🔧 Chores
- **Elfa**: Migrated to v2 API
- **Documentation**: Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev7...v0.6.7-dev8

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

## v0.6.7-dev6

### 🚀 Features
- **feat: add endpoint to retrieve current agent information** - Added new API endpoint to get current agent configuration
- **feat: add EVM and Solana wallet address fields to AgentResponse model** - Enhanced agent response model with blockchain wallet address support

### 🔧 Maintenance
- **chore: code formatting improvements in agent model response data** - Code style improvements for better maintainability

### 📖 Documentation
- **doc: changelog** - Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev5...v0.6.7-dev6

## v0.6.7-dev5

### 🚀 Improvements
- **improve: remove enabled parameter from add_autonomous_task skill** - Autonomous tasks are now always enabled by default for better user experience

### 📖 Documentation
- **doc: changelog** - Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev4...v0.6.7-dev5

## v0.6.7-dev4

### 🐛 Bug Fixes
- **fix: ensure proper serialization of autonomous tasks in agent operations** - Fixed serialization issues in autonomous task operations to ensure proper data handling

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev3...v0.6.7-dev4

## v0.6.7-dev3

### 🚀 Features
- **feat: add autonomous task info in entrypoint rules system prompt** - Enhanced autonomous task execution with better context information including task ID, name, description, and scheduling details

### 🐛 Bug Fixes
- **fix: autonomous skill bug** - Fixed issues related to autonomous skill execution

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev2...v0.6.7-dev3

## v0.6.7-dev2

### 🚀 Features

#### Autonomous Task Management System
- **feat: add autonomous task management system skills** - Added comprehensive system skills for managing autonomous tasks within agents
  - `system_add_autonomous_task` - Create new autonomous task configurations with custom prompts and scheduling
  - `system_delete_autonomous_task` - Remove existing autonomous task configurations  
  - `system_list_autonomous_tasks` - View all configured autonomous tasks for an agent
  - Enhanced core agent and skill systems to support autonomous task operations
  - Updated skill abstracts to provide better context handling for system operations

### 🐛 Bug Fixes
- **fix: format** - Code formatting improvements

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.7-dev1...v0.6.7-dev2

## v0.6.6

### 🚀 Features
- **Twitter Timeline Enhancement**: Exclude replies from twitter timeline by default to improve content quality and relevance

### 🔧 Technical Details
- Modified twitter timeline skill to filter out reply tweets by default
- This change improves the signal-to-noise ratio when fetching timeline data

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5...v0.6.6

## v0.6.5-dev8

### 🚀 Features
- **Twitter Timeline Enhancement**: Exclude replies from twitter timeline by default to improve content quality and relevance

### 🔧 Technical Details
- Modified twitter timeline skill to filter out reply tweets by default
- This change improves the signal-to-noise ratio when fetching timeline content

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev7...v0.6.5-dev8

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

## v0.6.5-dev7

### 📚 Documentation
- Better agent API documentation improvements

### 🐛 Bug Fixes
- Fixed typo in codebase

### 🔧 Improvements
- Prevent twitter reply skill from replying to own tweets

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev6...v0.6.5-dev7

## v0.6.5-dev6

### 🚀 Features
- Add sanitize_privacy method to ChatMessage model

### 📚 Documentation
- Update changelog for v0.6.5-dev4
- Change log updates

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev5...v0.6.5-dev6

## v0.6.5-dev5

### 📚 Documentation
- Update changelog for v0.6.5-dev4

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev4...v0.6.5-dev5

## v0.6.5-dev4

### 🐛 Bug Fixes
- Fixed agent data types
- Fixed bug in agent schema

### 🔄 Merged Pull Requests
- Merge pull request #711 from crestalnetwork/hyacinthus

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev3...v0.6.5-dev4

## v0.6.5-dev3

### 📚 Documentation
- Better agent documentation
- Updated changelog

### 🐛 Bug Fixes
- Remove number field in agent

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev2...v0.6.5-dev3

## v0.6.5-dev2

### 🐛 Bug Fixes
- **Database Connection**: Use separate connection for langgraph migration setup

### 📚 Documentation
- Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.5-dev1...v0.6.5-dev2

## v0.6.5-dev1

### 🚀 Features
- **Redis Database Configuration**: Added redis_db parameter to all redis connections for better database isolation and configuration flexibility

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.4...v0.6.5-dev1

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

## v0.6.3-dev2

### Chores
- Updated dependencies in pyproject.toml:
  - Updated `supabase` from `>=2.10.0` to `>=2.16.0`
  - Updated `openai` from `1.96.1` to `1.97.0`
  - Updated lock file accordingly

### Documentation
- Updated changelog

### Pull Requests
- Merged PR #705: chore: update dependencies in pyproject.toml

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.3-dev1...v0.6.3-dev2

## v0.6.3-dev1

### Features
- feat: add cdp swap skill for token swapping functionality (9a3ff94)

### Bug Fixes
- fix: lint error (9c6cfa5)
- fix: a type error (41f9f9a)

### Chores
- chore: update changelog (ef36cb6)
- chore: package versions (297c55d)
- chore: fix dependency error (453d3a1)

### Documentation
- doc: changelog (88bba96)

### Other
- tmp: now working (31385d3)
- Merge branch 'main' into hyacinthus (28b0b73)

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.2-dev2...v0.6.3-dev1

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

## v0.6.2-dev2

### 🚀 Features
- **Credit Event Tracking**: Added agent_wallet_address field to credit event tracking
- **Agent API Enhancement**: Enhanced agent API and authentication with improved documentation

### 🐛 Bug Fixes
- **API Key Skill**: Better get API key skill description

### 🔧 Improvements
- **Twitter Service**: Refactored twitter service for better performance

### 📚 Documentation
- **API Documentation**: Updated API documentation and restructured files
- **Change Log**: Updated change log documentation

### 🧹 Maintenance
- **Dependencies**: UV sync updates

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.2-dev1...v0.6.2-dev2

## v0.6.2-dev1

### 🚀 Features
- **Agent API Sub-application**: Added dedicated agent API sub-application with CORS and error handling
- **Flexible User ID**: Made user_id optional in chat API with agent.owner fallback for better usability

### 🔧 Improvements
- **Text Extraction**: Improved formatting in extract_text_and_images function
- **Authentication**: Updated agent API endpoints to use token-based authentication
- **Admin Auth**: Refactored admin authentication system
- **Agent Auth**: Refactored agent authentication system

### 🐛 Bug Fixes
- **Chat Message**: Fixed typo in chat message handling
- **Supabase Link**: Fixed Supabase link issue

### 📚 Documentation
- **README**: Updated documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.1-dev1...v0.6.2-dev1

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

## v0.6.1-dev1

### Features
- feat: add public key to supabase

### Bug Fixes
- fix: node log level
- fix: cdp get balance bug
- fix: close some default skills

### Documentation
- doc: changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.18...v0.6.1-dev1

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

## v0.6.0-dev.18

### Bug Fixes
- **CDP Wallet**: Fixed wallet creation during agent creation process
- **CDP Balance**: Fixed CDP get balance functionality

### Documentation
- Updated changelog

### Pull Requests
- Merged PR #700: Improve CDP wallet functionality and agent creation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.17...v0.6.0-dev.18

## v0.6.0-dev.17

### Changes
- Merge pull request #699 from crestalnetwork/hyacinthus
- refactor: cdp wallet

### What's Changed
- Refactored CDP wallet functionality to improve code organization and maintainability
- Enhanced CDP client implementation with better error handling and structure

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.16...v0.6.0-dev.17

## v0.6.0-dev.16

### Features
- Updated LLM integration guide and skill schema configurations
- Improved HTTP skill schema configuration
- Enhanced Supabase skill schema configuration

### Documentation
- Enhanced LLM.md with better integration guidelines
- Updated skill configuration documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.15...v0.6.0-dev.16

## v0.6.0-dev.15

### New Features
- **HTTP Skills**: Added comprehensive HTTP client skills for making web requests including GET, POST, PUT, DELETE operations
- **Major Framework Upgrades**: Merged comprehensive improvements from hyacinthus branch including:
  - AgentKit upgrade from 0.4.0 to 0.6.0
  - LangGraph upgrade to 0.5 with refactored core components
  - IntentKit package prepared for publishing

### Improvements
- **Web Scraper**: Enhanced capability to scrape whole sites in one prompt
- **Memory Optimization**: Use SQLite for testing environments
- **Stream Executor**: Refactored for better performance
- **Infrastructure**: Refactored IntentKit core architecture
- **Admin Schema**: Updated with correct skills path and WebP support

### Bug Fixes
- Fixed import bugs in core modules
- Fixed action cost calculation to exclude owner
- Fixed chat history validation with proper exception handling
- Fixed debug flag logic and logging
- Fixed Dune Analytics description and image issues
- Fixed summarize functionality bugs

### Development
- Fixed various lint issues across the codebase
- Updated dependencies with `uv sync`
- Improved testing infrastructure
- Added comprehensive LLM integration documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.14...v0.6.0-dev.15

## v0.6.0-dev.14

### Features
- Enhanced Supabase skills with improved data operations and error handling
- Added more fields to runnable config and skill context
- Added comprehensive Supabase skill category with conditional schema validation

### Improvements
- Better error handling across all Supabase data operations
- Improved data validation and type checking
- Enhanced base skill functionality for better reusability
- Updated core node functionality for better skill integration

### Technical Details
- Updated schema definitions for better data integrity
- Refined insert, update, upsert, and delete operations
- Improved token base skill implementation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.0-dev.13...v0.6.0-dev.14

## v0.6.0-dev.11

### Documentation
- Updated LLM integration guide and config documentation
- Enhanced developer documentation for better clarity

### Chores
- General maintenance and cleanup

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
