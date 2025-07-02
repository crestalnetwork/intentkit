from typing import Optional

from pydantic import BaseModel, Field


class VeniceImageEnhanceInput(BaseModel):
    """Input for Venice Image Enhance tool (scale=1, enhance=True)."""

    image_url: str = Field(
        description="The URL of the image to enhance. Must be a publicly accessible URL."
    )

    enhancePrompt: str = Field(
        ...,
        max_length=1500,
        description=(
            "Required prompt describing the desired enhancement style. "
            "Best used with short descriptors like 'gold', 'marble', or 'angry, menacing'."
        ),
    )

    replication: Optional[float] = Field(
        default=0.35,
        ge=0.1,
        le=1.0,
        description=(
            "How strongly lines and noise in the base image are preserved. "
            "Higher values retain more noise and detail but are less smooth."
        ),
    )

    enhanceCreativity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much the enhancement AI is allowed to change the image. "
            "0 = minimal change, 1 = generate a new image entirely."
        ),
    )
