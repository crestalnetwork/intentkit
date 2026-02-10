from __future__ import annotations

import hashlib
import json
from enum import IntEnum
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField


class AgentVisibility(IntEnum):
    """Agent visibility levels with hierarchical ordering.

    Higher values indicate broader visibility:
    - PRIVATE (0): Only visible to owner
    - TEAM (10): Visible to team members
    - PUBLIC (20): Visible to everyone
    """

    PRIVATE = 0
    TEAM = 10
    PUBLIC = 20


class AgentCore(BaseModel):
    """Agent core model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: Annotated[
        str | None,
        PydanticField(
            default=None,
            title="Name",
            description="Display name of the agent",
            max_length=50,
        ),
    ] = None
    picture: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Avatar of the agent",
        ),
    ] = None
    purpose: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Purpose or role of the agent",
            max_length=20000,
        ),
    ] = None
    personality: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Personality traits of the agent",
            max_length=20000,
        ),
    ] = None
    principles: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Principles or values of the agent",
            max_length=20000,
        ),
    ] = None
    # AI part
    model: Annotated[
        str,
        PydanticField(
            default="gpt-5-mini",
            description="LLM of the agent",
        ),
    ] = "gpt-5-mini"
    prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Base system prompt that defines the agent's behavior and capabilities",
            max_length=20000,
        ),
    ] = None
    prompt_append: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Additional system prompt that has higher priority than the base prompt",
            max_length=20000,
        ),
    ] = None
    temperature: Annotated[
        float | None,
        PydanticField(
            default=0.7,
            description="The randomness of the generated results is such that the higher the number, the more creative the results will be. However, this also makes them wilder and increases the likelihood of errors. For creative tasks, you can adjust it to above 1, but for rigorous tasks, such as quantitative trading, it's advisable to set it lower, around 0.2. (0.0~2.0)",
            ge=0.0,
            le=2.0,
        ),
    ] = 0.7
    frequency_penalty: Annotated[
        float | None,
        PydanticField(
            default=0.0,
            description="The frequency penalty is a measure of how much the AI is allowed to repeat itself. A lower value means the AI is more likely to repeat previous responses, while a higher value means the AI is more likely to generate new content. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
        ),
    ] = 0.0
    presence_penalty: Annotated[
        float | None,
        PydanticField(
            default=0.0,
            description="The presence penalty is a measure of how much the AI is allowed to deviate from the topic. A higher value means the AI is more likely to deviate from the topic, while a lower value means the AI is more likely to follow the topic. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
        ),
    ] = 0.0
    short_term_memory_strategy: Annotated[
        Literal["trim", "summarize"] | None,
        PydanticField(
            default="trim",
            description="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
        ),
    ] = "trim"
    wallet_provider: Annotated[
        Literal["cdp", "native", "readonly", "safe", "privy", "none"] | None,
        PydanticField(
            default=None,
            description="Provider of the agent's wallet",
        ),
    ] = None
    network_id: Annotated[
        Literal[
            "base-mainnet",
            "ethereum-mainnet",
            "polygon-mainnet",
            "arbitrum-mainnet",
            "optimism-mainnet",
            "bnb-mainnet",
            "solana",
            "base-sepolia",
        ]
        | None,
        PydanticField(
            default="base-mainnet",
            description="Network identifier",
        ),
    ] = "base-mainnet"
    skills: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Dict of skills and their corresponding configurations",
        ),
    ] = None

    def hash(self) -> str:
        """
        Generate a fixed-length hash based on the agent's content.

        The hash remains unchanged if the content is the same and changes if the content changes.
        This method serializes only AgentCore fields to JSON and generates a SHA-256 hash.
        When called from subclasses, it will only use AgentCore fields, not subclass fields.

        Returns:
            str: A 64-character hexadecimal hash string
        """
        hash_data = {}

        for field_name in AgentCore.model_fields:
            value = getattr(self, field_name)
            if value is not None:
                hash_data[field_name] = value

        json_str = json.dumps(hash_data, sort_keys=True, default=str, ensure_ascii=True)

        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
