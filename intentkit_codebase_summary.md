# IntentKit Codebase Summary

## Overview
IntentKit is a sophisticated autonomous AI agent framework built with Python that enables the creation and management of AI agents with blockchain interaction, social media management, and extensible skill capabilities. The platform is designed for scalable, autonomous agent deployment with robust payment systems and multi-platform integration.

## Core Architecture

### Technology Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL
- **AI/ML**: LangChain, LangGraph, OpenAI, DeepSeek, and other LLM providers
- **Storage**: PostgreSQL with pgvector for embeddings, Redis for caching/scheduling
- **Blockchain**: Coinbase Developer Platform (CDP), GOAT SDK, multiple wallet integrations
- **Package Management**: uv (recently migrated from Poetry)

### Key Components

#### 1. Agent Engine (`intentkit/core/engine.py`)
- **Central orchestration** of AI agent execution using LangGraph
- **Memory management** with PostgreSQL-based conversation history
- **Tool/skill loading** and dynamic initialization
- **Cost tracking** and payment integration
- **Multi-model support** with context length management
- **Recursive execution** with configurable limits

#### 2. Agent Management (`intentkit/core/agent.py`)
- **Agent configuration** storage and retrieval
- **Quota management** and cost analytics
- **Action cost calculation** with statistical analysis (avg, min, max, percentiles)
- **Credit system** integration for usage tracking

#### 3. Skill System (`intentkit/skills/`)
- **Extensible architecture** with 30+ pre-built skills
- **Base skill class** (`IntentKitSkill`) with rate limiting, error handling
- **Categories**: Blockchain (CDP, Token, DeFi), Social Media (Twitter, Telegram), Analytics (DexScreener, Dune, Moralis), AI (OpenAI, Image/Audio processing)
- **Dynamic skill loading** and configuration per agent

#### 4. Multiple Entrypoints (`app/entrypoints/`)
- **Web API** (`web.py`): REST API with JWT authentication, debug endpoints
- **Twitter** (`twitter.py`): OAuth 2.0 integration, tweet processing, timeline monitoring
- **Telegram** (`tg.py`): Bot integration with group/private chat support
- **Autonomous** (`autonomous.py`): Scheduled tasks with cron/interval support

## Key Features

### 1. Multi-Agent Support
- Each agent has unique configuration, skills, and memory
- Private vs public agent modes
- Agent ownership and access control
- Dynamic skill enabling/disabling per agent

### 2. Blockchain Integration
- **CDP Wallet**: Automatic wallet creation, balance checking, transaction execution
- **GOAT SDK**: Multi-chain support (EVM, Solana) with 15+ plugins
- **DeFi Integration**: Uniswap, 1inch, Jupiter, Superfluid protocols
- **NFT Support**: OpenSea integration for NFT operations

### 3. Autonomous Operation
- **Scheduler service** (`app/autonomous.py`) with Redis-backed job storage
- **Cron and interval-based** task execution
- **Heartbeat monitoring** for service health
- **Dynamic task management** based on agent configuration updates

### 4. Payment & Credit System
- **Sophisticated credit tracking** with upstream cost attribution
- **Usage analytics** and quota management
- **Fee structures** with agent owner revenue sharing
- **Free tier limits** with abuse prevention

### 5. Social Media Management
- **Twitter**: OAuth 2.0, tweet posting/replying, timeline monitoring, mentions processing
- **Telegram**: Bot creation, group management, dynamic enable/disable
- **Rate limiting** and API quota management per platform

## Database Architecture

### Core Models (`intentkit/models/`)
- **Agent**: Configuration, skills, prompts, autonomous tasks
- **AgentData**: Extended agent data and state management
- **ChatMessage**: Conversation history with skill call tracking
- **Credit**: Usage tracking and payment processing
- **User**: User management and authentication
- **Skill**: Skill configuration and state storage

## Development & Deployment

### Configuration
- Environment-based configuration (`intentkit/config/`)
- Support for development, staging, production environments
- Feature flags for debug mode, payment systems, authentication

### Docker Support
- Multi-service Docker Compose setup
- Separate services for different entrypoints
- Redis and PostgreSQL containerization
- Production-ready deployment configuration

### Security
- JWT-based authentication for admin APIs
- OAuth 2.0 for external service integration
- Environment variable management for secrets
- Sentry integration for error tracking

## Recent Developments (v0.5.0)
- Migration to `uv` package manager for faster dependency management
- Enhanced payment system with quota management
- Improved memory management with token-based cleanup
- New skill integrations (Elfa, DeFiLlama, CryptoCompare)
- GOAT SDK integration for expanded blockchain support

## Skill Ecosystem
The platform includes 30+ skills across categories:
- **Blockchain**: CDP operations, token management, DeFi protocols
- **Analytics**: DexScreener, Dune Analytics, Moralis, CoinGecko
- **Social**: Twitter operations, Slack notifications
- **AI**: OpenAI integration, image/audio processing
- **Data**: Web scraping, Tavily search, GitHub integration

## Architecture Strengths
1. **Modular design** enabling easy extension and customization
2. **Robust error handling** with comprehensive logging and monitoring
3. **Scalable architecture** supporting multiple concurrent agents
4. **Comprehensive testing** infrastructure with debug endpoints
5. **Production-ready** deployment with Docker and service monitoring

This codebase represents a mature, enterprise-grade AI agent platform suitable for both development and production deployment across various use cases including DeFi automation, social media management, and autonomous task execution.