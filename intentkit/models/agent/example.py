from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel
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
