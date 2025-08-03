import logging
import os
from typing import Any, Dict, Literal, Optional, Type

import httpx
from langchain_core.callbacks.manager import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from intentkit.skills.unrealspeech.base import UnrealSpeechBaseTool

logger = logging.getLogger(__name__)


class TextToSpeechInput(BaseModel):
    """Input for TextToSpeech tool."""

    text: str = Field(description="The text to convert to speech. Required.")

    voice_id: str = Field(
        description="The voice ID to use for speech synthesis. Options include: 'af_bella', 'af_sarah', 'af_nicole', 'af_sky', 'am_adam', 'am_michael', 'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis'.",
        default="af_sarah",
    )

    bitrate: str = Field(
        description="The audio bitrate. Higher values provide better quality but larger file sizes. Options: '64k', '96k', '128k', '192k', '256k', '320k'.",
        default="192k",
    )

    speed: float = Field(
        description="The speech speed adjustment. Range: -1.0 (slower) to 1.0 (faster), with 0.0 being the normal speed.",
        default=0.0,
    )

    timestamp_type: Optional[Literal["word", "sentence"]] = Field(
        description="The type of timestamps to include in the response. 'word' for word-level timestamps, 'sentence' for sentence-level, or None for no timestamps.",
        default="word",
    )


class TextToSpeech(UnrealSpeechBaseTool):
    """Tool for converting text to speech using UnrealSpeech's API.

    This tool converts text to natural-sounding speech in various voices.
    It can generate speech with different voices, speeds, and qualities.
    The response includes URLs to the audio file and optional word-level timestamps.
    """

    name: str = "text_to_speech"
    description: str = (
        "Converts text to natural-sounding speech using UnrealSpeech.\n"
        "Use this tool when you need to generate spoken audio from text.\n"
        "Returns URLs to the generated audio file and word-level timestamps.\n"
        "Provides various voice options and speech customization parameters."
    )
    args_schema: Type[BaseModel] = TextToSpeechInput

    def get_env_var(self, env_var_name: str) -> Optional[str]:
        """Helper method to get environment variables."""
        return os.environ.get(env_var_name)

    async def _arun(
        self,
        text: str,
        voice_id: str = "af_sarah",
        bitrate: str = "192k",
        speed: float = 0.0,
        timestamp_type: Optional[Literal["word", "sentence"]] = "word",
        config: Optional[Any] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run the tool to convert text to speech."""

        # Get the API key from context config if available
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category) if config else None
        api_key = (
            skill_config.get("api_key", None) if context and skill_config else None
        )

        # Clean up and validate input
        if not text:
            return {"success": False, "error": "Text cannot be empty."}

        # Validate bitrate
        valid_bitrates = ["64k", "96k", "128k", "192k", "256k", "320k"]
        if bitrate not in valid_bitrates:
            logger.warning(f"Invalid bitrate '{bitrate}'. Using default '192k'.")
            bitrate = "192k"

        # Validate speed
        if not -1.0 <= speed <= 1.0:
            logger.warning(
                f"Speed value {speed} is outside valid range (-1.0 to 1.0). Clamping to valid range."
            )
            speed = max(-1.0, min(1.0, speed))

        try:
            # For longer text, use the /speech endpoint for better handling
            endpoint = "https://api.v8.unrealspeech.com/speech"

            # Prepare the request payload
            payload = {
                "Text": text,
                "VoiceId": voice_id,
                "Bitrate": bitrate,
                "Speed": str(speed),
                "Pitch": "1",
                "OutputFormat": "uri",
            }

            # Add timestamp type if specified
            if timestamp_type:
                payload["TimestampType"] = timestamp_type

            # Send the request to UnrealSpeech API
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                response = await client.post(endpoint, json=payload, headers=headers)

                # Check response status
                if response.status_code != 200:
                    logger.error(f"UnrealSpeech API error: {response.text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code} - {response.text}",
                    }

                # Parse response
                result = response.json()

                # Format the response
                return {
                    "success": True,
                    "task_id": result.get("TaskId"),
                    "audio_url": result.get("OutputUri"),
                    "timestamps_url": result.get("TimestampsUri")
                    if timestamp_type
                    else None,
                    "status": result.get("TaskStatus"),
                    "voice_id": result.get("VoiceId"),
                    "character_count": result.get("RequestCharacters"),
                    "word_count": result.get("RequestCharacters", 0)
                    // 5,  # Rough estimate
                    "duration_seconds": result.get("RequestCharacters", 0)
                    // 15,  # Rough estimate (15 chars/sec)
                    "created_at": result.get("CreationTime"),
                }

        except Exception as e:
            logger.error(f"Failed to generate speech: {e}", exc_info=True)
            return {"success": False, "error": f"Failed to generate speech: {str(e)}"}
