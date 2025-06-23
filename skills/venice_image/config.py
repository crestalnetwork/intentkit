from typing import Optional

from pydantic import BaseModel, Field


class VeniceImageConfig(BaseModel):
    """Skill Config for Venice Image."""

    api_key_provider: str = Field(
        default="agent_owner",
        description="Provider of the API Key, could be agent_owner or platform",
    )
    safe_mode: bool = Field(
        default=True,
        description="Whether to use safe mode. If enabled, this will blur images that are classified as having adult content",
    )
    hide_watermark: bool = Field(
        default=True,
        description="Whether to hide the Venice watermark. Venice may ignore this parameter for certain generated content.",
    )
    embed_exif_metadata: bool = Field(
        default=False, description="Whether to embed EXIF metadata in the image."
    )
    negative_prompt: str = Field(
        default="(worst quality: 1.4), bad quality, nsfw",
        description="The default negative prompt used when no other prompt is provided.",
    )
    rate_limit_number: Optional[int] = Field(
        default=None,
        description="Maximum number of allowed calls within the specified time window.",
    )
    rate_limit_minutes: Optional[int] = Field(
        default=None,
        description="Duration of the time window (in minutes) for rate limiting.",
    )
