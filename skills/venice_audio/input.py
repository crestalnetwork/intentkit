from typing import Literal, Optional

from pydantic import BaseModel, Field

# Define the allowed format literals based on the API documentation
AllowedAudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class VeniceAudioInput(BaseModel):
    """
    Input schema for Venice AI Text-to-Speech (/audio/speech endpoint).
    Defines parameters controllable by the user when invoking the tool.
    """

    input: str = Field(
        ...,  # Ellipsis (...) indicates this field is required
        description="The text to generate audio for. Maximum length is 4096 characters.",
        min_length=1,  # As per API docs: Required string length: 1
        max_length=4096,  # As per API docs: The maximum length is 4096 characters.
    )

    speed: Optional[float] = Field(
        default=1.0,  # As per API docs: default: 1 (using float for consistency)
        description="The speed of the generated audio. 1.0 is normal speed. Allowed range: 0.25 to 4.0.",
        ge=0.25,  # As per API docs: Required range: 0.25 <= x
        le=4.0,  # As per API docs: Required range: x <= 4
    )

    response_format: Optional[AllowedAudioFormat] = Field(
        default="mp3",  # As per API docs: default: mp3
        description="The desired audio format for the output file.",
    )

    # --- Note on other API parameters ---
    # 'model': Currently hardcoded to 'tts-kokoro' in VeniceAudioBaseTool._arun. Could be added here if needed.
    # 'voice': Handled by the 'voice_model' attribute of the specific VeniceAudioBaseTool instance. Not typically set via input schema.
    # 'streaming': Currently hardcoded to False in VeniceAudioBaseTool._arun. Could be added here if streaming support is implemented.
