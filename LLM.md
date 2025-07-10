# LLM Integration Guide for IntentKit

This guide provides comprehensive information for Large Language Models (LLMs) working with the IntentKit autonomous agent framework.

## Project Overview

IntentKit is an autonomous agent framework that enables creation and management of AI agents with capabilities.

## Architecture Understanding

1. **IntentKit Package** (`intentkit/`)
   - The intentkit/ folder is published as a pip package.
   - The core/ folder contains the agent system, driven by LangGraph.
   - The models/ folder houses the entity models, most of it both have padantic models for memory use and sqlalchemy models for storage.
   - The config/ folder contains the system level config, like database config, LLM provider api keys and skill provider api keys.
   - The skills/ folder contains the skills system, driven by LangChain's BaseTool. LLM can call skills to fetch data, perform actions, or interact with the environment.
   - The utils/ folder contains the utility functions, like logging, formatting, etc.
   - The abstracts/ folder contains interfaces, for core/ and skills/ use.

2. **IntentKit App** (`app/`)
   - The app/ folder contains API server, autonomous runner, and background scheduler.
   - User can use intentkit package in their own project for customization, or just start the intentkit app for default features.

3. **Operation or Temporary Scripts** (`scripts/`)
   - Agent management scripts
   - Manual scripts for potential use
   - Migration scripts

4. **Integration Tests** (`tests/`)
   - Core package testing in `tests/core/`
   - API server testing in `tests/api/`
   - Skill integration testing in `tests/skills/`

## Technology Stack
- Package manager: uv, please use native `uv` command, do not use the `uv pip` command.
- Lint: ruff, run `uv run ruff format & uv run ruff check --fix` after your final edit.
- API framework: fastapi, Doc in https://fastapi.tiangolo.com/
- DB ORM: SQLAlchemy 2.0, please check the 2.0 api for use, do not use the legacy way. Doc in https://docs.sqlalchemy.org/en/20/
- Model: Pydantic V2, Also be careful not to use the obsolete V1 interface. Doc in https://docs.pydantic.dev/latest/
- Testing Framework: pytest

## Rules

1. Always use the latest version of the new package.
2. Always use English for code comments.
3. Always use English to search.

## Dev Guide

### Skills Development

1. Skills are in the `intentkit/skills/` folder. Each folder is a category. Each skill category can contain multiple skills. A category can be a theme or a brand.
2. To avoid circular dependencies, Skills can only depend on the contents of models, abstracts, utils, and clients.
3. The necessary elements in a skill category folder are as follows. For the paradigm of each element, you can refer to existing skills, such as skills/twitter
   - `base.py`: Base class inherit `IntentKitSkill`. If there are functions that are common to this category, they can also be written in BaseClass. A common example is get_api_key
   - Then every skill can have it's own file, with the same name as the skill. Key points:
      - The skill class inherit BaseClass created in base.py
      - The `name` attribute need a same prefix as the category name, such as `twitter_`, for uniqueness in the system.
      - The `description` attribute is the description of the skill, which will be used in LLM to select the skill.
      - The `args_schema` attribute is the pydantic model for the skill arguments.
      - The `_arun` method is the main logic of the skill. There is special parameter `config: RunnableConfig`, which is used to pass the LangChain runnable config. There is function `context_from_config` in IntentKitSkill, can be used to get the context from the runnable config. In the _arun method, if there is any exception, just raise it, and the exception will be handled by the Agent. If the return value is not a string, you can document it in the description attribute.
   - The `__init__.py` must have the function `async def get_skills( config: "Config", is_private: bool, store: SkillStoreABC, **_,) -> list[OpenAIBaseTool]`
      - Config is inherit from `SkillConfig`, and the `states` is a dict, key is the skill name, value is the skill state. If the skill category have any other config fields need agent creator to set, they can be added to Config.
      - If the skill is stateless, you can add a global _cache for it, to avoid re-create the skill object every time.
   - A square image is needed in the category folder.
   - Add schema.json file for the config, since the Config inherit from SkillConfig, you can check examples in exists skill category to find out the pattern.

## Ops Guide

### Git Commit
1. run `uv run ruff format && uv run ruff check --fix` before commit.
2. When you generate git commit message, always start with one of feat/fix/chore/docs/test/refactor/improve. Title Format: `<type>: <subject>`, subject should start with lowercase. Only one-line needed, do not generate commit message body.

### Github Pull Request
1. If there are uncommited changes, add them and commit them.
2. Push to remote branch.
3. Pull origin/main, so you can summarize the changes for pull request title and description.
4. Create a pull request with MCP tools.

### Github Release
1. Please use gh command to do it.
2. Make a `git pull` first.
3. The release number rule is: pre-release is vX.X.X-devX, release is vX.X.X.
4. Find the last version number in release or pre-release using `git tag`, diff origin/main with it, summarize the release note to build/changelog.md for later use. Calculate the version number of this release. Add a diff link to release note too, the from and to should be the version number.
5. And also insert the release note to the beginning of CHANGELOG.md (This file contains all history release notes, don't use it in gh command), leave this changed CHANGELOG.md in local, don't commit and push it, we will commit it together with next changes.
6. Construct `gh release create` command, calculate the next version number, use changelog.md as notes file in gh command.
7. Use gh to do release only, don't create branch, tag, or pull request.
