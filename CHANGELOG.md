## v0.8.72

### New Features

- Added httpx compatibility layer for X402 payment protocol skills, enabling better HTTP request handling and improved integration

### Improvements

- Improved QuickNode network alias handling for better blockchain network compatibility
- Enhanced network mapping for Arbitrum and Optimism chains in QuickNode integration

### Bug Fixes

- Fixed bugs in QuickNode network alias normalization module

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.71...v0.8.72

## v0.8.71

### Features
- Added prefunding support for Privy wallets in x402 safe payment operations

### Improvements
- Improved payment strategy for x402 safe transactions
- Enhanced x402 base module functionality

### Bug Fixes
- Fixed issues in the x402 payment module
- Fixed linting errors

### Documentation
- Added copilot instruction file

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.70...v0.8.71

## v0.8.70

### Improvements
- Updated wallet provider system with enhanced support for Safe and Privy modes
- Improved x402 payment validation
- Updated dependencies (async-lru, boto3, botocore)
- Code formatting improvements

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.69...v0.8.70

## v0.8.69

### Bug Fixes

- Fixed x402 payment signing with Safe wallets by adding support for specifying the address that holds funds
- Fixed chat memory clearing functionality to directly delete from database tables

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.68...v0.8.69

## v0.8.66

### Bug Fixes
- Fixed JSON serialization issues in x402 payment signing with Privy wallets

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.65...v0.8.66

## v0.8.65

### Bug Fixes
- Fixed x402 payment signing issues in Privy wallet integration

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.64...v0.8.65

## v0.8.64

### Bug Fixes
- Fixed autonomous task selection to correctly filter out archived agents
- Improved test stability by removing unused variables in Safe deployment tests

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.63...v0.8.64

## v0.8.63

### Bug Fixes
- Fixed transaction collision issues in Safe wallet deployment operations
- Improved reliability of module configuration after Safe deployment
- Added local nonce tracking to prevent race conditions with distributed RPC nodes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.62...v0.8.63

## v0.8.62

### Bug Fixes
- Fixed intermittent GS026 errors in Safe wallet operations by adding deployment visibility check
- Safe contracts are now verified to be visible across RPC nodes before proceeding with module operations

### Improvements
- Added `_wait_for_safe_deployed` function with retry logic to handle RPC node synchronization delays
- Improved reliability of Safe wallet deployments in distributed RPC environments

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.61...v0.8.62

## v0.8.61


### Bug Fixes
- Fixed Safe wallet deployment on L2 networks (Base, Base Sepolia, BNB Chain) by using correct L2 singleton addresses

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.60...v0.8.61

## v0.8.60

### Bug Fixes
- Fixed critical nonce collision issue in Safe wallet deployments under high concurrency

### Improvements
- Improved transaction reliability for multi-worker deployments

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.59...v0.8.60

## v0.8.59 - 2026-01-14

### New Features
- Server authorization keys are now automatically integrated into key quorums, enabling both server and users to independently control wallets while maintaining security
- Added `get_authorization_public_keys()` method to expose server public keys for key quorum creation

### Improvements
- Authorization keys are now loaded and cached during initialization for better performance and reliability
- Improved JSON canonicalization with proper primitive type handling for better signature consistency
- Added validation to ensure Privy owner IDs start with 'did:privy:' prefix
- Authorization signature support now applies to all Privy RPC calls including send_transaction
- Enhanced logging with key fingerprints for easier debugging of authorization issues

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.58...v0.8.59


## v0.8.58 - 2026-01-14

### New Features
- Added Privy authorization signature support using ECDSA signatures for enhanced API security
- Support for multiple authorization keys via `PRIVY_AUTHORIZATION_KEYS` environment variable

### Improvements
- Fixed spending limit synchronization when agent configuration changes, ensuring allowance module settings are properly updated

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.57...v0.8.58

## v0.8.57 - 2026-01-14

### New Features
- Added key quorum support for Privy wallets, enabling multi-signature configurations with customizable authorization thresholds
- Added configurable Privy base URL for flexible API endpoint configuration

### Improvements
- Fixed circular dependencies in agent and user modules by using dynamic imports
- Improved agent post tags field handling with proper null normalization
- Enhanced Privy wallet creation with key quorum signer support

### Bug Fixes
- Fixed type casting issues in Web3 transaction parameter handling
- Improved Safe deployment event parsing for better address extraction
- Updated test suite to match new agent model structure

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.56...v0.8.57

## v0.8.56 - 2026-01-13

### New Features
- Added gasless transaction support for Safe wallets using the relayer pattern
- Safe wallet owners can now execute transactions without holding ETH for gas

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.55...v0.8.56

## v0.8.55 - 2026-01-13

### New Features
- Added user server wallet creation system with Safe smart accounts
- Added UserData model for flexible key-value storage per user

### Improvements
- Refactored agent list endpoint to use dynamic template rendering

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.54...v0.8.55

## v0.8.54 - 2026-01-13

### New Features
- Added BNB Smart Chain (bnb-mainnet) support across all chain configurations
- Pass Privy user ID as wallet owner when creating agent wallet

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.53...v0.8.54

## v0.8.53 - 2026-01-13

### Bug Fixes
- Fixed Privy signing methods to use correct RPC methods for different use cases (personal_sign for messages, secp256k1_sign for raw hashes)

### Dependencies
- Updated dependencies via uv sync

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.52...v0.8.53

## v0.8.52 - 2026-01-13

### Bug Fixes
- Fixed Privy signMessage method to use correct API method and encoding parameters

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.51...v0.8.52

## v0.8.51 - 2026-01-13

### Bug Fixes
- Fixed Safe nonce retrieval to handle empty '0x' response from RPC, defaulting to 0 instead of failing

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.50...v0.8.51

## v0.8.50 - 2026-01-13

### Bug Fixes
- Fixed Safe CREATE2 address calculation bug - the initializer should only be included in the salt calculation, not in the deploymentData
- Added address validation to ensure predicted address matches actual deployed address

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.49...v0.8.50

## v0.8.49 - 2026-01-12

### Bug Fixes
- Fixed wallet processing when creating agents from templates
- Wallet initialization now properly triggered during template-based agent creation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.48...v0.8.49

## v0.8.48 - 2026-01-12

### New Features
- **Local Chat Interface**: New local chat functionality with private mode
- **Agent UI Improvements**: Redesigned agent creation and editing pages
- **Post System**: Added post creation, viewing, and timeline features
- **Chat Sidebar**: Enhanced chat UI with conversation history
- **Agent Activities**: New activity tracking and viewing for agents

### Improvements
- Better frontend navigation and user experience
- Enhanced skill availability management
- Improved agent template handling with dynamic field application

### Bug Fixes
- Fixed issues in agent network ID enum handling
- Resolved bugs in post-related modules
- Fixed UI bugs in agent update and skill state mapping
- Patched Pydantic upgrade compatibility issues

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.47...v0.8.48

## v0.8.45 - 2026-01-08

### New Features
- **x402 Payment Protocol Skills**: Added two new skills for working with 402-protected resources:
  - `x402_check_price`: Check the price of a paid API resource before making a payment
  - `x402_pay`: Perform paid HTTP requests with configurable maximum payment limits

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.44...v0.8.45

## v0.8.44 - 2026-01-07

### New Features
- **x402 Payment Protocol Skills**: Added two new skills for working with 402-protected resources:
  - `x402_check_price`: Check the price of a paid API resource before making a payment
  - `x402_pay`: Perform paid HTTP requests with configurable maximum payment limits

### Improvements
- Enhanced agent creation with field descriptions and validation
- Improved credit and asset management for agents
- Refined scheduler and engine components
- Better Privy wallet client integration

### Documentation
- Clarified documentation on folder structure and local development setup
- Updated operational guides for release management

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.43...v0.8.44

## v0.8.43 - 2026-01-07

### Features
- Support recovery of partially created Privy wallets

### Fixes
- Fix core API to hide from public docs
- Fix test issue

### Tests
- Add new tests for core engine functionality
- Add new tests for credit system
- Add new tests for scheduler
- Improve agent asset tests

### Documentation
- Refactor LLM docs
- Fix ops guide
- Add skill development guide
- Add operations guide
- Update changelog

### Dependencies
- Upgrade dependencies via uv sync

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.42...v0.8.43

## v0.8.42 - 2025-01-31

### Features
- Added Pydantic field descriptions to `AgentCreationFromTemplate` for better API documentation and clarity
- Enhanced validation in `AgentUpdate` to include `extra_prompt` field, preventing level 1 and level 2 headings

### Improvements
- Updated test coverage to verify optional fields (readonly_wallet_address, weekly_spending_limit, extra_prompt) are correctly passed through during agent creation from templates

### Documentation
- Added descriptive field documentation for all parameters in agent creation from template

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.41...v0.8.42

## v0.8.41 - 2025-01-29

### Features
- **Agent Visibility System**: Added public/private agent visibility controls, allowing agents to be marked as public or private for better access management
- **Jupiter Skill Integration**: New Jupiter skill for Solana DeFi operations including token price queries and swap functionality
- **Enhanced Template Creation**: Improved agent template creation with support for visibility settings and additional field mappings

### Improvements
- **Prompt Structure**: Refined prompt structure and formatting for better clarity and consistency
- **Template Fields**: Added more comprehensive field support when creating agents from templates

### Bug Fixes
- **Template Agent Creation**: Fixed field mapping issues in template-based agent creation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.40...v0.8.41

## v0.8.40 - 2025-01-31

### Features
- **Autonomous Error Tracking**: Added comprehensive error activity tracking for autonomous task execution. The system now automatically creates agent activities when tasks fail, return empty responses, or encounter unexpected errors, improving error visibility and debugging capabilities.
- **Memory Management**: Added `has_memory` flag support for autonomous tasks, allowing fine-grained control over thread memory persistence per task execution.

### Bug Fixes
- **Changelog Generation**: Fixed bug in changelog generation process.

### Technical Details
- Enhanced `run_autonomous_task` function with error detection and activity creation
- Improved error handling for empty responses, system errors, and exceptions
- Added proper logging for error activity creation failures

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.39...v0.8.40

## v0.8.39 - 2026-01-04

### Features
- **Safe Smart Wallet Integration**: Implemented Safe smart wallet functionality with Privy wallet provider for enhanced security and multi-signature support
- **Agent Activity & Post Modules**: Added comprehensive agent activity and post modules with complete models, core logic, and unit tests
- **System Skills**: Introduced system skills for creating posts and activities, enabling agents to interact with the platform
- **Skill Call Agent**: Implemented skill call agent functionality with improved error handling and validation
- **Default System Skills**: System skills are now included by default for all agents

### Improvements
- **Unified Agent API Router**: Refactored auth and openai_compatible endpoints into a unified agent_api router for better organization
- **Better Error Handling**: Enhanced error messages and handling in call agent skill
- **Agent Post Skill**: Improved agent post skill functionality

### Testing
- Added comprehensive unit tests for template functions including `create_template_from_agent` and `render_agent`

### Maintenance
- Upgraded dependencies to latest versions
- Fixed various lint issues

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.38...v0.8.39

## v0.8.38 - 2025-12-31

### Features
- **Template System**: Added comprehensive agent template functionality
  - New `Template` model for storing reusable agent configurations
  - Template rendering system that applies template fields to agents
  - Support for `extra_prompt` field when creating agents from templates
  - Template management API endpoints in admin interface

### Refactoring
- **Agent Retrieval Architecture**: Moved template rendering logic from model layer to core layer
  - Created new `get_agent()` function in `core/agent.py` for centralized agent retrieval with template rendering
  - Deprecated `Agent.get()` method with backward compatibility maintained
  - Updated all non-model code to use new `get_agent()` function
  - Cleaner separation of concerns between data models and business logic

### Improvements
- Refactored `send_slack_message()` to have no return value for cleaner async handling
- Enhanced code organization and maintainability

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.37...v0.8.38

## v0.8.37 - 2025-12-27

### Features
- Frontend skill box display in chat interface
- Local frontend development improvements
- GPT image model updated to version 1.5

### Fixes
- Docker compose configuration fixes
- Debug authentication removed
- Various lint fixes

### Chores
- Dependency updates

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.36...v0.8.37

## v0.8.35 - 2025-11-30

### Features
- Add GPT-5.2 model with enhanced capabilities (1.75 input pricing, 14 output pricing)
- Add Gemini 3 Pro Preview model support
- Add OpenRouter provider integration for additional model access
- Add DeepSeek 3.2 model support
- Filter available models based on provider API key presence
- Initialize frontend application with Next.js
  - Agent management interface
  - Dashboard with agent cards
  - Responsive UI with Tailwind CSS
- Add checkpoint cleanup functionality in core engine
- Add cleanup scheduler for automatic maintenance

### Improvements
- Reorganize llm.csv model entries for better readability
- Enhanced LLM model filtering logic
- Add comprehensive tests for LLM model functionality

### Fixes
- Remove readonly router and service for cleaner architecture
- Resolve linting errors and deprecation warnings across codebase
- Fix type hints and import statements
- Update error handling utilities

### Documentation
- Add AGENTS.md with detailed frontend architecture guidelines
- Update CHANGELOG.md with recent changes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.34...v0.8.35

## v0.8.34 - 2025-11-28

### Features
- Add LangGraph 2.0 checkpoints table migration
- Add dev and prod docker image tags for releases
- Keep short memory only 90 days
- Add daily scheduled task to clean up old LangGraph checkpoints, writes, and blobs
- Team model support
- Add draft functionality and manager module
- Third party S3 support
- Autonomous use internal service to chat
- Agent testing capabilities
- Move checker to core

### Fixes
- Reorder checkpoint migration steps to drop columns after pk update
- Cache checkpointer
- Improve checkpointer clean
- Clean old generator model
- Cache by agent deploy
- Change node to middleware
- Fix astream bug
- Add basedpyright to llm.md

### Refactoring
- Migrate checkpointer to shallow saver implementation
- Migrate langchain agent middleware
- Move s3 to clients

### Chores
- Remove EKS deployment steps from CI workflow
- Disable kubectl deployments in build workflow
- Disable autonomous, telegram, and checker deployments in testnet-dev
- Remove x402 server
- Upgrade dependencies (uv sync --upgrade)

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.33...v0.8.34

## v0.8.33 - 2025-11-14

### Bug Fixes
- Fixed lifi bug in token execution
- Updated code formatting with ruff

### Documentation
- Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.32...v0.8.33

## v0.8.32 - 2025-11-14

### Fixes
- Add default value to x402 price field in agent model
- Update changelog documentation

**Changes:**
- Changed x402_price default from None to 0.01 in AgentPublicInfo model
- Updated changelog with v0.8.31 release notes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.31...v0.8.32

## v0.8.31 - 2025-11-14

### Changes
- Updated multiple dependencies to latest versions
- Enhanced LLM model configurations
- Updated agent model definitions

**Dependency Updates:**
- langchain-mcp-adapters: 0.1.12 → 0.1.13
- langgraph-prebuilt: 1.0.2 → 1.0.4  
- MCP: 1.21.0 → 1.21.1
- OpenAI: 2.7.2 → 2.8.0
- Ruff: 0.14.4 → 0.14.5
- Slack SDK: 3.37.0 → 3.38.0

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.30...v0.8.31

## v0.8.30 - 2025-11-13

### Features
- System prompt now support search and super functionality

### Documentation
- Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.29...v0.8.30

## v0.8.29 - 2025-11-13

### Bug Fixes
- Fixed engine.py with latest changes

### Documentation
- Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.28...v0.8.29

## v0.8.28 - 2025-11-13

### Changes
- chore: release prep
- chore: uv sync

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.27...v0.8.28

## v0.8.24 - 2025-11-11

### Configuration Updates
- Updated uv.lock dependencies with 243 changes
- Enhanced configuration system in `intentkit/config/config.py`
- Updated LLM model configurations in `intentkit/models/llm.csv`
- Added new LLM model support in `intentkit/models/llm.py`

### Documentation
- Updated CHANGELOG.md with recent changes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.23...v0.8.24

## v0.8.23 - 2025-11-10

### Bug Fixes
- Enhanced chain utility functions with better error handling
- Improved ENS resolution with fallback mechanisms
- Updated logging and error reporting
- Fixed various bugs in utility functions

### Features
- Added comprehensive test coverage for chain utilities
- Enhanced ENS utilities for improved reliability
- Improved agent and chat model functionality
- Updated configuration handling

### Improvements
- Refactored chain utility functions for better performance
- Enhanced error handling in various components
- Dependency updates and optimizations
- Improved code organization and structure

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.22...v0.8.23

## v0.8.22

### Features
- **feat: get user by wallet** - Added functionality to retrieve user by wallet address
- Enhanced user model with wallet lookup capabilities
- Added comprehensive tests for wallet-based user retrieval

### Improvements
- **refactor**: restructure to root only pyproject config for better project organization
- **chore**: update uv.lock dependencies for latest security and performance updates
- **build**: updated build configuration and package files

### Documentation
- Updated x402 documentation with demo information
- Enhanced changelog documentation

### Technical Details
- Updated `intentkit/models/user.py` with wallet lookup functionality
- Added comprehensive tests in `tests/models/test_user.py`
- Multiple model updates for better structure and organization
- Updated build workflows and configuration files

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.21...v0.8.22

## v0.8.21

### Bug Fixes
- Fixed moralis assets bug in core/asset.py
- Updated related tests in tests/core/test_agent_asset.py
- Updated changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.20...v0.8.21
## v0.8.20

### Features
- Updated changelog with latest changes
- Improvements to GPT avatar generator functionality

### Technical Details
- Enhanced GPT avatar generator with better error handling and functionality
- Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.19...v0.8.20

## v0.8.19

### Bug Fixes
- **Credit System**: Updated credit system logic in core credit module
- **Skill Author Handling**: Fixed skill author handling in credit calculations

### Technical Details
- Updated `intentkit/core/credit.py` with improved logic
- All linting checks passed
- No breaking changes

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.18...v0.8.19

## v0.8.18

### Features
- Updated OpenAI image generation skills configuration
- Enhanced image generation capabilities

### Changes
- Updated `intentkit/skills/openai/gpt_avatar_generator.py`
- Updated `intentkit/skills/openai/gpt_image_mini_generator.py`
- Added changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.17...v0.8.18

## v0.8.17

### Features
- **feat: update openai gpt avatar generator and skills metadata** - Enhanced OpenAI GPT avatar generator functionality with improved skills metadata
- **feat: add gpt avatar generator skill** - Added new GPT avatar generator skill to the OpenAI skills collection

### Bug Fixes
- **fix: a import bug** - Fixed import issue in the codebase

### Other Changes
- Updated dependency lock file (uv.lock)
- Code formatting and linting improvements

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.16...v0.8.17

## v0.8.16

### Documentation
- **docs: update x402 documentation and fix icon bug (#885)** - Updated x402 API documentation with latest changes
- **docs: add x402 api documentation** - Added comprehensive x402 API documentation

### Bug Fixes
- **fix: icon bug** - Fixed icon-related bug in the application

### Other Changes
- **doc: changelog** - Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.15...v0.8.16

## v0.8.15

### Bug Fixes
- **x402 error handling**: Improved error handling mechanisms for x402 operations
- **x402 message bug**: Fixed message processing issues in x402 integration
- **documentation**: Updated changelog and documentation

### Features
- Enhanced x402 skill integration with better reliability and functionality

### Summary
This release focuses on improving the x402 integration with better error handling and message processing capabilities.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.14...v0.8.15

## v0.8.14

### Features
- **x402 Skill Improvements**: Updated x402 skill image format from PNG to WebP for better performance and smaller file size
- **Model Configuration Updates**: Enhanced agent and LLM model configurations for improved functionality
- **Schema Updates**: Updated x402 skill schema configuration

### Changes
- Converted x402 skill image from PNG to WebP format
- Updated `intentkit/models/agent.py` with improved agent model configurations
- Updated `intentkit/models/llm.py` with enhanced LLM model configurations
- Updated `intentkit/skills/x402/schema.json` with latest skill schema
- Removed temporary analysis script `analyze_schema_defs.py`
- Updated dependencies in `uv.lock`

### Impact
- Improved performance with WebP image format
- Better model configurations for enhanced functionality
- Cleaner codebase with removal of temporary files

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.13...v0.8.14

## v0.8.13

### New Features
- **X402 Server Implementation**: Complete x402 server implementation with routing and API endpoints
- **Base Onchain Skill Class**: Added foundational class for onchain operations and blockchain interactions
- **EVM Account Support**: Enhanced EVM account management capabilities for better blockchain integration

### Improvements
- **API Updates**: Enhanced API functionality and x402 ask agent capabilities
- **CDP Client Refactor**: Improved CDP (Coinbase Developer Platform) client implementation for better reliability and performance

### Bug Fixes
- **X402 Router**: Fixed x402 router bug for improved stability
- **X402 Input Schema**: Corrected x402 input schema validation
- **API Routing**: Fixed x402 path commenting in API routing

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.12...v0.8.13

## v0.8.12

### Features
- **feat: update asset scheduler and llm model configuration** - Enhanced asset scheduler functionality, improved core scheduler operations, and updated LLM model configuration in CSV file

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.11...v0.8.12

## v0.8.11

### New Features
- **Import Checking Scripts**: Added comprehensive import validation tools to maintain code quality
  - `check_imports.py` - Basic import validation script
  - `check_imports_comprehensive.py` - Advanced import analysis with circular dependency detection  
  - `simple_import_check.py` - Lightweight import checker

### Improvements
- **Code Quality**: Automated code formatting updates across multiple skill modules
- **Developer Tools**: Enhanced dependency management and organization capabilities
- **CI/CD Ready**: Scripts can be integrated into continuous integration pipelines

### Benefits
- Early detection of circular dependencies
- Improved code quality through automated import validation
- Better dependency management and organization
- Consistent code formatting across the codebase

### Changes
- Added 3 new import checking scripts in the `scripts/` directory
- Code formatting updates across 32+ skill module files
- Enhanced development workflow with automated quality assurance tools

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.10...v0.8.11

## v0.8.10

### Bug Fixes
- **fix: improve token address handling in wallet prompt** - Updated the prompt message in `_build_wallet_section` to provide clearer guidance on when to use `token_search` skill. Improved the logic for token address resolution by specifying that the skill should be used when only a token symbol is provided and the address cannot be found in context. Added network_id reference to make the prompt more specific about which chain to search on.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.9...v0.8.10

## v0.8.9

### Features
- **feat: update wallet section in prompt** - Enhanced wallet section building logic in `_build_wallet_section` function and improved prompt handling for wallet-related operations

### Bug Fixes
- **fix: update dockerfile configuration** - Updated Dockerfile configuration for better deployment

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.8...v0.8.9

## v0.8.7

### Bug Fixes
- **Telegram Event Loop Handling**: Improved stability and reliability of the telegram integration by fixing event loop handling

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.6...v0.8.7

## v0.8.6

### Bug Fixes
- **Checker and Scheduler Modules**: Updated checker and scheduler modules to improve functionality
- **Readonly Instance**: Removed readonly instance to fix configuration issues

### Maintenance
- **Dependencies**: Upgraded dependencies with uv sync --upgrade

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.5...v0.8.6

## v0.8.5

### Bug Fixes
- **Clear Change Functionality**: Restored functionality for clearing changes in the system
- **Draft Chat Bug**: Fixed issues with draft chat functionality that were preventing proper message handling
- **Private Skill Bug**: Resolved bugs related to private skills system that were affecting skill execution

### Documentation
- **Changelog Updates**: Updated changelog documentation for better release tracking

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.4...v0.8.5

## v0.8.4

### New Features
- **CDP Client Enhancement**: Enhanced CDP client implementation with improved configuration management
- **Agent Configuration**: Updated agent configurations for better functionality

### Improvements
- **Skill Schemas**: Updated skill schemas for cookiefun and twitter integrations
- **Build Workflow**: Enhanced build workflow configuration
- **Documentation**: Updated LLM documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.3...v0.8.4

## v0.8.3

### Bug Fixes
- **Clear command detection**: Fixed the logic for correctly detecting clear commands in the system

### Maintenance
- **Dependencies**: Updated project dependencies and changelog to reflect recent changes
- **Code quality**: Applied linting and formatting improvements

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.2...v0.8.3

## v0.8.2

### New Features
- **Improved @clear command matching**: Enhanced the @clear command with case-insensitive regex matching and support for both @clear and /clear formats
  - Case-insensitive matching: Now supports @Clear, @CLEAR, /Clear, /CLEAR, etc.
  - Multiple formats: Added support for both @clear and /clear commands
  - Word boundary matching: Uses regex with  to ensure exact word matching
  - Trim support: Messages are trimmed before matching to handle whitespace

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.1...v0.8.2

## v0.8.1

### New Features
- **Agent Slug Enhancement**: Automatically update agent slug with EVM wallet address when slug is empty

### Maintenance
- Updated uv.lock dependencies for improved compatibility and security
- Updated project configuration and dependencies

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.8.0...v0.8.1

## v0.8.0

### New Features
- **Agent System Enhancements**: Enhanced agent deployment with wallet processing and notifications
- **Agent Fields**: Added new agent fields and public schema support
- **LLM and Skills Management**: Added centralized LLM and skills CSV model files
- **S3 File Storage**: Added generic S3 file storage helper functionality
- **Agent Response Validation**: Added required field validation for agent name in JSON schema

### Improvements
- **Code Quality**: Improved type annotations and error handling throughout the agent system
- **Agent Model**: Refactored agent model schema with public schema support
- **Agent Core**: Major refactoring of agent core functionality
- **Skill Store**: Changed skill store to agent store for better organization
- **LiFi Functions**: Added annotations to LiFi functions
- **Account Balance**: Improved account balance checking precision with diagnostic script

### Bug Fixes
- **Environment Configuration**: Fixed environment example configuration
- **Scheduler**: Fixed duplicate job errors by adding replace_existing=True to scheduler jobs
- **Telegram**: Fixed Telegram uvloop issues
- **Coinbase Dependencies**: Dropped coinbase langchain dependency
- **SQLite Compatibility**: Fixed incompatible SQLite SQL issues
- **Fee Validation**: Commented out fee validation and set default wallet provider to CDP
- **Agent Deployment**: Fixed agent deployment issues and variable naming conflicts
- **HTTP Errors**: Improved HTTP error handling
- **Agent Response**: Fixed agent response model validation and data conversion

### Refactoring
- **Agent Provider Icons**: Replaced agentkit provider icons
- **Code Formatting**: Improved code formatting and removed unused imports
- **Agent Model**: Major refactoring of agent model structure
- **Engine**: Fixed various engine bugs
- **User Model**: Fixed user model issues

### Documentation
- **Agent Documentation**: Added agents documentation symlink
- **Changelog**: Updated changelog documentation

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.7.4...v0.8.0

## v0.7.4

### Features
- **Memory Management**: Auto clear error memory for improved agent performance

### Bug Fixes
- **Code Quality**: Lint improvements

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.7.3...v0.7.4

## v0.7.3

### Features
- **Telegram Bot Enhancements**: Major improvements to telegram bot functionality
  - Added telegram bot owner configuration and message routing for better control
  - Added processing reactions to telegram bot messages for user feedback
  - Updated telegram bot processing reaction emoji to thinking face for better UX
  - Added telegram unauthorized error handling and failed agents cache for improved reliability

### Bug Fixes
- **Telegram Bot Fixes**: 
  - Updated telegram bot reactions to use ReactionTypeEmoji format for proper display
  - Removed redundant reply_to_message_id in AI relayer error handling

### Technical Improvements
- Enhanced error handling and caching mechanisms
- Improved message routing and bot configuration
- Better reaction handling and emoji formatting

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.7.2...v0.7.3

## v0.7.2

### Features
- Updated firecrawl skill with improved configuration and base implementation
- Enhanced agent generator configuration

### Bug Fixes
- Fixed credit system precision and transaction type handling
- Added SQL script for fixing existing transaction types

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.7.1...v0.7.2

## v0.7.1

### Features
- **Database**: Add connection health check and max lifetime to pool
- **Credit System**: Add transaction statistics tracking to credit accounts
- **Account Checking**: Enhance balance consistency check with detailed verification

### Bug Fixes
- Add database initialization and improve account filtering in migration script
- Use direct permanent_profit field from database in agent statistics
- Ensure decimal precision with quantize in credit calculations
- Add missing amount fields to CreditTransactionTable instantiations in refill function

### Documentation
- Update changelog

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.7.0...v0.7.1

## v0.7.0

### Features
- **Config Enhancement**: Add intentkit_prompt to config and prompt system for better customization
- **Credit Management**: Add comprehensive credit event consistency checker with base validation
- **Migration Tools**: Add script to migrate credit accounts from transactions
- **Optimization**: Optimize credit event consistency checking scripts for better performance

### Fixes
- **Model Update**: Change default model to gpt-5-mini for improved performance
- **Credit Events**: Update and improve credit event consistency check script
- **Workflow**: Update pypi publish workflow and changelog

### Refactoring
- **Credit Event Logic**: Improve readability of credit type distribution logic
- **Performance**: Remove redundant logs and add batch stats tracking for better monitoring

### Chores
- **Documentation**: Update LLM rules and guidelines
- **Migration Scripts**: Fix and improve migration scripts

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.26...v0.7.0

## v0.6.26

### Refactoring
- Move asyncio import to top of file in account_checking.py

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.6.25...v0.6.26

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
- If you open the jwt verify of admin api, it now ignore the request come from internal network
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
