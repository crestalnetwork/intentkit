from pydantic import BaseModel, Field, HttpUrl


class VeniceImageVision(BaseModel):
    """Input for the Image Vision tool."""

    image_url: HttpUrl = Field(
        description="The URL of the image to to be described by the Vision model. Must be a publicly accessible URL.",
    )
