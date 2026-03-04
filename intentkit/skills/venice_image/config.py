from pydantic import BaseModel, Field


class VeniceImageConfig(BaseModel):
    """Skill Config for Venice Image."""

    api_key_provider: str = Field(
        default="agent_owner",
        description="API key provider: agent_owner or platform.",
    )
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
    rate_limit_number: int | None = Field(
        default=None,
        description="Max calls within the time window.",
    )
    rate_limit_minutes: int | None = Field(
        default=None,
        description="Time window in minutes for rate limiting.",
    )
