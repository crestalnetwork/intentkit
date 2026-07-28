from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

from intentkit.models.agent.tags import AgentTag


class AgentExample(BaseModel):
    """Agent example configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: Annotated[
        str,
        PydanticField(
            description="Name of the example",
            max_length=50,
        ),
    ]
    description: Annotated[
        str,
        PydanticField(
            description="Description of the example",
            max_length=200,
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Example prompt",
            max_length=2000,
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
        ),
    ] = 0.01
    external_website: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Link of external website of the agent, if you have one",
            json_schema_extra={
                "format": "uri",
            },
        ),
    ] = None
    ticker: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Ticker symbol of the agent",
            max_length=10,
            min_length=1,
        ),
    ] = None
    token_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Token address of the agent",
            max_length=66,
        ),
    ] = None
    token_pool: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Pool of the agent token",
            max_length=66,
        ),
    ] = None
    fee_percentage: Annotated[
        Decimal | None,
        PydanticField(
            default=None,
            description="Fee percentage of the agent",
            ge=Decimal("0.0"),
        ),
    ] = None
    example_intro: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Introduction of the example",
            max_length=2000,
        ),
    ] = None
    examples: Annotated[
        list[AgentExample] | None,
        PydanticField(
            default=None,
            description="List of example prompts for the agent",
            max_length=6,
        ),
    ] = None
    tags: Annotated[
        list[str] | None,
        PydanticField(
            default=None,
            description="Tags for categorizing the agent",
            max_length=10,
        ),
    ] = None
    public_extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Public extra data of the agent",
        ),
    ] = None


class AgentPublishInput(BaseModel):
    """Request body for publishing an agent to public.

    Carries only the four user-collected fields: ``description`` (a core
    agent field) plus three public-info fields. Anything else on
    ``AgentPublicInfo`` (ticker, token_*, x402_price, fee_percentage,
    public_extra, external_website) is intentionally not accepted here —
    callers should leave existing values on the agent untouched and let
    the platform fill in fee_percentage server-side.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="AgentPublishInput",
        extra="forbid",
    )

    description: str = PydanticField(
        ...,
        min_length=1,
        max_length=1000,
        description="Public description of the agent",
    )
    example_intro: str = PydanticField(
        ...,
        min_length=1,
        max_length=2000,
        description="Intro shown above the example prompts in a new chat",
    )
    examples: list[AgentExample] = PydanticField(
        ...,
        min_length=1,
        max_length=6,
        description="Example prompts (1-6) shown to users in a new chat",
    )
    tags: list[AgentTag] | None = PydanticField(
        None,
        max_length=3,
        description="Up to 3 category tags from the predefined list",
    )

    def to_public_info(self) -> "AgentPublicInfo":
        """Build the canonical AgentPublicInfo for the publish flow.

        Forces ``fee_percentage = 1`` and leaves all other public-info fields
        unset so existing values on the agent are preserved by the
        partial-update merge in ``apply_public_info_update``. ``description``
        is a core agent field, not public info — the publish flow writes it
        separately.
        """
        return AgentPublicInfo(
            example_intro=self.example_intro,
            examples=self.examples,
            tags=[t.value for t in self.tags] if self.tags is not None else None,
            fee_percentage=Decimal("1"),
        )
