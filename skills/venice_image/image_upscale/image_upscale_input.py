from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class VeniceImageUpscaleInput(BaseModel):
    """Input for the Image Upscale tool."""

    image_url: HttpUrl = Field(
        description="The URL of the image to upscale. Must be a publicly accessible URL.",
    )
    scale: Literal[2, 4] = Field(
        default=2,
        description="The factor by which to upscale the image (either 2 or 4). Defaults to 2.",
    )
