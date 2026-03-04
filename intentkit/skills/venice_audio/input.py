from typing import Literal

from pydantic import BaseModel, Field

# Define the allowed format literals based on the API documentation
AllowedAudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class VeniceAudioInput(BaseModel):
    """Input schema for Venice AI Text-to-Speech."""

    voice_input: str = Field(
        ...,
        description="Text to generate audio for (max 4096 chars).",
        min_length=1,
        max_length=4096,
    )

    voice_model: str = Field(description="Voice model for TTS generation.")

    speed: float | None = Field(
        default=1.0,
        description="Audio speed, 0.25-4.0. Default 1.0.",
        ge=0.25,
        le=4.0,
    )

    response_format: AllowedAudioFormat | None = Field(
        default="mp3",
        description="Output audio format.",
    )

    # --- Note on other API parameters ---
    # 'model': Currently hardcoded to 'tts-kokoro' in VeniceAudioBaseTool._arun. Could be added here if needed.
    # 'voice': Handled by the 'voice_model' attribute of the specific VeniceAudioBaseTool instance. Not typically set via input schema.
    # 'streaming': Currently hardcoded to False in VeniceAudioBaseTool._arun. Could be added here if streaming support is implemented.
