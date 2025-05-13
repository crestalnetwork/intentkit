# Building Skills for IntentKit

This guide will help you create new skills for IntentKit. Skills are the building blocks that give agents their capabilities.

## Overview

Skill can be enabled in the Agent configuration. The Agent is aware of all the skills it possesses and will spontaneously use them at appropriate times, utilizing the output of the skills for subsequent reasoning or decision-making. The Agent can call multiple skills in a single interaction based on the needs.

A skill in IntentKit is a specialized tool that inherits from `IntentKitSkill` (which inherits from LangChain's `BaseTool`). Each skill provides specific functionality that agents can use to interact with external services or perform specific tasks.

## How skill works

Before writing our first skill, we need to understand how a skill works.

The code of skills are all in the `skills/` directory. Each subdirectory is a skill category.

The skill is configured in the field `skills` in the agent configuration. The key is the skill category, and the value is a predefined skill config. For example:
```yaml
id: my-test-agent
skills:
  twitter:
    states: 
      get_timeline: public
      post_tweet: private
      follow_user: disabled
  common:
    states:
      current_time: public
```

## Adding a new skill category

Most of the time, you will need to add a new skill category. If you only want to add a skill in an existing category, you can copy an existing skill and modify it. Let's see how to add a new skill category.

After creating a new skill category folder in `skills/`, you need to add these 4 essential components:
- `base.py` - Defines the base class for the skill, adding shared functionality for all skills in this category
- `your_skill_name.py` - Defines the first skill implementation in the new category
- `__init__.py` - Defines how to instantiate and retrieve the skills in this category
- `schema.json` - Defines the config JSON schema for this skill category to help users understand the configuration options
- An icon for the skill category, png/svg/jpg/jpeg is supported. Tips: most of the time you can easily find the icon from their github organization or X account.

Let's use `common/current_time` as an example.

### Base class (base.py)

The base class should inherit from `IntentKitSkill` and provide common functionality for all skills in this category:

```python
from typing import Type

from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill


class CommonBaseTool(IntentKitSkill):
    """Base class for common utility tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "common"
```

Key points:
- The base class should inherit from `IntentKitSkill`
- Define common attributes all skills in this category will use
- Implement the `category` property to identify the skill category
- Include the `skill_store` for persistence if your skills need to store data

### Skill class (current_time.py)

Each skill implementation should inherit from your category base class:

```python
class CurrentTimeInput(BaseModel):
    """Input for CurrentTime tool."""

    timezone: str = Field(
        description="Timezone to format the time in (e.g., 'UTC', 'US/Pacific', 'Europe/London', 'Asia/Tokyo'). Default is UTC.",
        default="UTC",
    )


class CurrentTime(CommonBaseTool):
    """The doc string will not pass to LLM, it is written for human"""

    name: str = "current_time"
    description: str = (
        "Get the current time, converted to a specified timezone.\n"
        "You must call this tool whenever the user asks for the time."
    )
    args_schema: Type[BaseModel] = CurrentTimeInput

    async def _arun(self, timezone: str = "UTC", **kwargs) -> str:
        # Implementation of the tool
        # ...
```

Key points:
- Create a Pydantic model for the input parameters
- Inherit from your category base class
- Define required attributes: `name`, `description`, and `args_schema`
- Implement the logic in `_arun` (asynchronous) method

You should know, the `name`, `description`, and the description of the `args_schema` will be passed to the LLM. They are important reference information, letting LLM know when to call this skill, so please make sure they are clear and concise.

### Skill getter (__init__.py)

The `__init__.py` file exports your skills and defines how they are configured:

```python
from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.common.base import CommonBaseTool
from skills.common.current_time import CurrentTime

# Cache skills at the system level, because they are stateless
_cache: dict[str, CommonBaseTool] = {}


class SkillStates(TypedDict):
    current_time: SkillState


class Config(SkillConfig):
    """Configuration for common utility skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CommonBaseTool]:
    """Get all common utility skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [get_common_skill(name, store) for name in available_skills]


def get_common_skill(
    name: str,
    store: SkillStoreABC,
) -> CommonBaseTool:
    """Get a common utility skill by name."""
    if name == "current_time":
        if name not in _cache:
            _cache[name] = CurrentTime(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown common skill: {name}")
```

Key points:
- Define a `TypedDict` for the skill states
- Create a `Config` class that extends `SkillConfig`
- Implement the `get_skills` function to return all enabled skills based on configuration
- The last param `**_` of `get_skills` is required. It is a placeholder for future use.
- Implement a helper function to instantiate individual skills
- Consider caching skill instances if they are stateless

### Config Schema (schema.json)

The schema.json file defines the JSON schema for configuring skills in this category:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "Common Utility Skills",
  "description": "Configuration schema for common utility skills",
  "properties": {
    "states": {
      "type": "object",
      "properties": {
        "current_time": {
          "type": "string",
          "title": "Current Time",
          "enum": [
            "disabled",
            "public",
            "private"
          ],
          "description": "State of the current_time skill"
        }
      },
      "description": "States for each common utility skill (disabled, public, or private)"
    }
  },
  "required": ["states"],
  "additionalProperties": true
}
```

Key points:
- Follow the JSON Schema standard (draft-07)
- Define the structure of the skill config, it will be used or check by the agent creation/update/import/export
- List all skills in the `states` section

## Testing your skills before creating PR

Make sure you have a local agent running, and you can test your skills in the agent.

Read [Development Guide](../../DEVELOPMENT.md) to get started with your setup.

You can test your skills using either API calls or the IntentKit Sandbox UI. The UI provides a visual interface for interacting with agents and testing skills. See the [IntentKit Sandbox UI repository](https://github.com/bluntbrain/intentkit-sandbox-ui) for setup and usage.

## More details

### About the return value

You may notice that we defined the input of the skill but not the output. What can I output?

The answer is everything. You can output a natural language string to LLM, or you can output an object, which will be converted to json and sent to LLM. You can even output a markdown, but you need to convert it to a string.

Images, videos and files are not supported yet. We will update the way to output images soon.

### How to handle errors

When the skill fails, you can return a string that will be passed to LLM. You can also raise an exception, which will be caught by the framework and converted to a string.

Only if you are not satisfied with the contents of the exception, you can catch it and add more context, then re-throw it.

### How to get the agent id in skill

We recommend that you write your skill as stateless, which helps save memory. When you need to get the runtime context, you can get it from the parameters of the _run function.

```python
from langchain_core.runnables import RunnableConfig

class YourSkillInput(BaseModel):
    foo: str = Field(description="A string parameter")
    bar: int = Field(description="An integer parameter")

class YourSkill(TwitterBaseTool):
    async def _arun(self, config: RunnableConfig, **kwargs) -> str:
        context = self.context_from_config(config)
        print(context)
        return f"I'm running in agent {context.agent.id}"
```

Here is the context definition:

```python
class SkillContext(BaseModel):
    agent: Agent
    config: SkillConfig
    user_id: str
    entrypoint: Literal["web", "twitter", "telegram", "trigger"]
```

If you have optional parameters in _arun, you can put them after `config: RunnableConfig`. Because the agent always use parameter name to pass the parameters.

### How to add custom skill config

Some times you may need to add custom config to the skill. Like an api key, or behavior choices for agents.

In `__init__.py`

```python
class Config(SkillConfig):
    """Configuration for your skills."""

    states: SkillStates
    api_key: str
```

Then it can be defined in the agent config.
```yaml
id: my-test-agent
skills:
  your_new_skill_category:
    states:
      your_skill: public
    api_key: your_api_key
```

You can get it from context when you need it.

### How to use more packages in skill

Please find in the [pyproject.toml](https://github.com/crestalnetwork/intentkit/blob/main/pyproject.toml) for the available packages.

Like for http client, we suggest you use the async client of `httpx`.

If you need to use other packages, please add them to the pyproject.toml use `poetry add`.

### How to store data in skill

You can use the [skill_store](https://github.com/crestalnetwork/intentkit/blob/main/abstracts/skill.py) to store data in the skill. It is a key-value store that can be used to store data that is specific to the skill.

You can store and retrieve a dict at these levels:
- agent
- thread
- agent + user

### How to write on-chain skills

You can use the [CdpClient](https://github.com/crestalnetwork/intentkit/blob/main/clients/cdp.py) to write on-chain skills.

Get the agent id from context, then use agent id and self.store to initialize the CdpClient.

### How to add api key to system level

You may want to add an api key of specific service to the system level.
Then every agent can share this api key, no longer need to add it in the config.

When you contribute a new skill category, please add it in skill config first.
If we find it is a common service, the IntentKit team will add it to the system level.
