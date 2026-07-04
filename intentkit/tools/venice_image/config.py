from pydantic import BaseModel, Field


class VeniceImageConfig(BaseModel):
    """Default settings for Venice Image tools."""

    safe_mode: bool = Field(
        default=True,
        description="Blur adult content if enabled.",
    )
    hide_watermark: bool = Field(
        default=True,
        description="Hide Venice watermark.",
    )
    embed_exif_metadata: bool = Field(
        default=False, description="Embed EXIF metadata in the image."
    )
    negative_prompt: str = Field(
        default="(worst quality: 1.4), bad quality, nsfw",
        description="Default negative prompt.",
    )
