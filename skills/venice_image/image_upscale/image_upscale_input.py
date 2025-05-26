from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class VeniceImageUpscaleInput(BaseModel):
    """Input for the Image Upscale tool."""

    image_url: HttpUrl = Field(
        description="The URL of the image to upscale. Must be a publicly accessible URL.",
    )
    replication: Optional[float] = Field(
        default=0.35,
        description=(
            'How strongly lines and noise in the base image are preserved. Higher values are noisier but less plastic/AI "generated"/hallucinated. Must be between 0.1 and 1.'
            "Required range: 0.1 <= x <= 1"
        ),
    )
    scale: Literal[2, 4] = Field(
        default=2,
        description="The factor by which to upscale the image (either 2 or 4). Defaults to 2.",
    )
