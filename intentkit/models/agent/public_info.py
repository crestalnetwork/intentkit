from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField


class AgentExample(BaseModel):
    """Agent example configuration."""

    name: Annotated[
        str,
        PydanticField(
            description="Name of the example",
            max_length=50,
            json_schema_extra={
                "x-placeholder": "Add a name for the example",
            },
        ),
    ]
    description: Annotated[
        str,
        PydanticField(
            description="Description of the example",
            max_length=200,
            json_schema_extra={
                "x-placeholder": "Add a short description for the example",
            },
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Example prompt",
            max_length=2000,
            json_schema_extra={
                "x-placeholder": "The prompt will be sent to the agent",
            },
        ),
    ]


class AgentPublicInfo(BaseModel):
    """Public information of the agent."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="AgentPublicInfo",
        from_attributes=True,
    )

    x402_price: Annotated[
        float | None,
        PydanticField(
            default=0.01,
            description="Price($) of the x402 request",
            ge=0.01,
            le=1.0,
            json_schema_extra={
                "x-placeholder": "USDC price per request",
                "x-step": 0.01,
            },
        ),
    ]
    description: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Description of the agent, for public view, not contained in prompt",
            json_schema_extra={
                "x-placeholder": "Introduce your agent",
            },
        ),
    ]
    external_website: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Link of external website of the agent, if you have one",
            json_schema_extra={
                "x-placeholder": "Enter agent external website url",
                "format": "uri",
            },
        ),
    ]
    ticker: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Ticker symbol of the agent",
            max_length=10,
            min_length=1,
            json_schema_extra={
                "x-placeholder": "If one day, your agent has it's own token, what will it be?",
            },
        ),
    ]
    token_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Token address of the agent",
            max_length=66,
            json_schema_extra={
                "x-placeholder": "The contract address of the agent token",
            },
        ),
    ]
    token_pool: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Pool of the agent token",
            max_length=66,
            json_schema_extra={
                "x-placeholder": "The contract address of the agent token pool",
            },
        ),
    ]
    fee_percentage: Annotated[
        Decimal | None,
        PydanticField(
            default=None,
            description="Fee percentage of the agent",
            ge=Decimal("0.0"),
            json_schema_extra={
                "x-placeholder": "Agent will charge service fee according to this ratio.",
            },
        ),
    ]
    example_intro: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Introduction of the example",
            max_length=2000,
            json_schema_extra={
                "x-placeholder": "Add a short introduction in new chat",
            },
        ),
    ]
    examples: Annotated[
        list[AgentExample] | None,
        PydanticField(
            default=None,
            description="List of example prompts for the agent",
            max_length=6,
            json_schema_extra={
                "x-inline": True,
            },
        ),
    ]
    public_extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Public extra data of the agent",
        ),
    ]
