# Skills Development Guide

This guide provides detailed information for developing skills in IntentKit.

## Overview

Skills are in the `intentkit/skills/` folder. Each folder is a category. Each skill category can contain multiple skills. A category can be a theme or a brand.

## Dependency Rules

To avoid circular dependencies, Skills can only depend on the contents of models, abstracts, utils, and clients.

## Skill Category Structure

The necessary elements in a skill category folder are as follows. For the paradigm of each element, you can refer to existing skills, such as `skills/twitter`:

### 1. Base Class (`base.py`)

Base class inherit `IntentKitSkill`. If there are functions that are common to this category, they can also be written in BaseClass. A common example is `get_api_key`.

### 2. Individual Skill Files

Each skill should have its own file, with the same name as the skill. Key points:

- **Class Inheritance**: The skill class inherit BaseClass created in `base.py`

- **Name Attribute**: The `name` attribute needs a same prefix as the category name, such as `twitter_`, for uniqueness in the system.

- **Description Attribute**: The `description` attribute is the description of the skill, which will be used in LLM to select the skill.

- **Args Schema**: The `args_schema` attribute is the pydantic model for the skill arguments.

- **Main Logic (`_arun` method)**: The `_arun` method is the main logic of the skill. 
  - There is special parameter `config: RunnableConfig`, which is used to pass the LangChain runnable config. 
  - There is function `context_from_config` in IntentKitSkill, can be used to get the context from the runnable config. 
  - In the `_arun` method, if there is any exception, just raise it, and the exception will be handled by the Agent. 
  - If the return value is not a string, you can document it in the description attribute.

### 3. Initialization (`__init__.py`)

The `__init__.py` must have the function:
```python
async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[OpenAIBaseTool]
```

- **Config**: Config is inherit from `SkillConfig`, and the `states` is a dict, key is the skill name, value is the skill state. If the skill category have any other config fields need agent creator to set, they can be added to Config.

- **Caching**: If the skill is stateless, you can add a global `_cache` for it, to avoid re-create the skill object every time.

- **Availability Check**: The `__init__.py` must also have the function:
```python
def available() -> bool:
    """Check if this skill category is available based on system config."""
```
This function checks if all required system configuration variables exist. If the skill requires a platform-hosted API key (e.g., `config.tavily_api_key`), return whether that key is present. If the skill has no system config dependencies (e.g., only uses agent-owner provided keys), return `True`.


### 4. Visual Assets

A square image is needed in the category folder.

### 5. Configuration Schema (`schema.json`)

Add `schema.json` file for the config, since the Config inherit from `SkillConfig`, you can check examples in exists skill category to find out the pattern. 

The `x-tags` in schema should be in this list: AI, Analytics, Audio, Communication, Crypto, DeFi, Developer Tools, Entertainment, Identity, Image, Infrastructure, Knowledge Base, NFT, Search, Social

## Exception Handling

There is no need to catch exceptions in skills, because the agent has a dedicated module to catch skill exceptions. If you need to add more information to the exception, you can catch it and re-throw the appropriate exception.