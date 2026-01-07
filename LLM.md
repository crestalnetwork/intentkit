# LLM Integration Guide for IntentKit

This guide provides comprehensive information for Large Language Models (LLMs) working with the IntentKit autonomous agent framework.

## Project Overview

IntentKit is an autonomous agent framework that enables creation and management of AI agents with capabilities.

## Architecture Understanding

1. **IntentKit Package** (`intentkit/`)
   - The intentkit/ folder is published as a pip package.
   - The intentkit/core/ folder contains the agent system, driven by LangGraph.
   - The intentkit/models/ folder houses the entity models, most of it both have padantic models for memory use and sqlalchemy models for storage.
   - The intentkit/config/ folder contains the system level config, like database config, LLM provider api keys and skill provider api keys.
   - The intentkit/skills/ folder contains the skills system, driven by LangChain's BaseTool. LLM can call skills to fetch data, perform actions, or interact with the environment.
   - The intentkit/utils/ folder contains the utility functions, like logging, formatting, etc.
   - The intentkit/abstracts/ folder contains interfaces, for core/ and skills/ use.

2. **IntentKit App** (`app/`)
   - The app/ folder contains local API server, autonomous runner, and background scheduler.
   - User can use intentkit package in their own project for customization, or just start the intentkit local API and frontend for local development or single-user use(no-auth).

3. **Operation or Temporary Scripts** (`scripts/`)
   - Agent management scripts
   - Manual scripts for potential use
   - Migration scripts

4. **Integration Tests** (`tests/`)
   - Core package testing in `tests/core/`
   - API server testing in `tests/api/`
   - Skill integration testing in `tests/skills/`

5. **Frontend** (`frontend/`)
   - The frontend/ folder contains the Next.js application for managing agents.
   - See `frontend/AGENTS.md` for detailed architecture and development guidelines.

## Technology Stack
- Package manager: uv
- Virtual environment: .venv, please use `source .venv/bin/activate` at least once to active virtual environment before running any command.
- Lint: ruff, run `ruff format & ruff check --fix` after your final edit.
- Language Server: BasedPyright, please make sure the changed files have no `basedpyright` errors.
- API framework: fastapi, Doc in https://fastapi.tiangolo.com/
- DB ORM: SQLAlchemy 2.0, please check the 2.0 api for use, do not use the legacy way. Doc in https://docs.sqlalchemy.org/en/20/
- Model: Pydantic V2, Also be careful not to use the obsolete V1 interface. Doc in https://docs.pydantic.dev/latest/
- Testing Framework: pytest, run `pytest` after your final edit.

## Rules

1. Always use the latest version of the new package.
2. Always use English for code comments.
3. Always use English to search.
4. Unless I specifically ask you to do so, do not git commit after coding.
5. Always place imports at the beginning of the file in your new code.
6. After implementing the functionality, there is no need to write dedicated documentation or example scripts.

## Dev Guide

### IntentKit Source Code

1. To avoid circular dependencies, we'll establish an order for packages in the intentkit/ folder, where packages on the left can never import packages on the right: utils, config, models, abstracts, clients, skills, core

### Skills Development

**When you need to develop or modify skills**, read the detailed guide: `agent_docs/skill_development.md`

## Ops Guide

**When you need to perform Git commits, pull requests, or releases**, read the detailed guide: `agent_docs/ops_guide.md`
