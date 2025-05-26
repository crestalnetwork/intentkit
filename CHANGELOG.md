# Changelog

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
