import hashlib
import json
import logging
from typing import Any, Dict, Optional, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.venice_audio.base import VeniceAudioBaseTool
from intentkit.skills.venice_audio.input import AllowedAudioFormat, VeniceAudioInput
from intentkit.utils.s3 import FileType, store_file_bytes

logger = logging.getLogger(__name__)

base_url = "https://api.venice.ai"


class VeniceAudioTool(VeniceAudioBaseTool):
    """
    Tool for generating audio using the Venice AI Text-to-Speech API (/audio/speech).
    It requires a specific 'voice_model' to be configured for the instance.
    Handles API calls, rate limiting, storage, and returns results or API errors as dictionaries.

    On successful audio generation, returns a dictionary with audio details.
    On Venice API error (non-200 status), returns a dictionary containing
    the error details from the API response instead of raising an exception.
    """

    name: str = "venice_audio_text_to_speech"
    description: str = (
        "Converts text to speech using a configured Venice AI voice model. "
        "Requires input text. Optional parameters include speed (0.25-4.0, default 1.0) "
        "and audio format (mp3, opus, aac, flac, wav, pcm, default mp3)."
    )
    args_schema: Type[BaseModel] = VeniceAudioInput
    skill_store: SkillStoreABC = Field(
        description="The skill store instance for accessing system/agent configurations and persisting data."
    )

    async def _arun(
        self,
        input: str,
        voice_model: str,
        speed: Optional[float] = 1.0,
        response_format: Optional[AllowedAudioFormat] = "mp3",
        **kwargs,  # type: ignore
    ) -> Dict[str, Any]:
        """
        Generates audio using the configured voice model via Venice AI TTS /audio/speech endpoint.
        Stores the resulting audio using store_file_bytes.
        Returns a dictionary containing audio details on success, or API error details on failure.
        """
        context = self.get_context()
        final_response_format = response_format if response_format else "mp3"
        tts_model_id = "tts-kokoro"  # API model used

        try:
            # --- Setup Checks ---
            api_key = self.get_api_key()

            _, error_info = self.validate_voice_model(context, voice_model)
            if error_info:
                return error_info

            if not api_key:
                message = (
                    f"Venice AI API key configuration missing for skill '{self.name}'."
                )
                details = f"API key not found for category '{self.category}'. Please configure it."
                logger.error(message)
                return {
                    "error": True,
                    "error_type": "ConfigurationError",
                    "message": message,
                    "details": details,
                    "voice_model": voice_model,
                    "requested_format": final_response_format,
                }

            if not voice_model:
                message = (
                    f"Instance of {self.name} was created without a 'voice_model'."
                )
                details = "Voice model must be specified for this tool instance."
                logger.error(message)
                return {
                    "error": True,
                    "error_type": "ConfigurationError",
                    "message": message,
                    "details": details,
                    "voice_model": voice_model,
                    "requested_format": final_response_format,
                }

            await self.apply_rate_limit(context)

            # --- Prepare API Call ---
            payload: Dict[str, Any] = {
                "model": tts_model_id,
                "input": input,
                "voice": voice_model,
                "response_format": final_response_format,
                "speed": speed if speed is not None else 1.0,
                "streaming": False,
            }

            payload = {k: v for k, v in payload.items() if v is not None}

            logger.debug(
                f"Venice Audio API Call: Voice='{voice_model}', Format='{final_response_format}', Payload='{payload}'"
            )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            api_url = f"{base_url}/api/v1/audio/speech"

            # --- Execute API Call ---
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                logger.debug(
                    f"Venice Audio API Response: Voice='{voice_model}', Format='{final_response_format}', Status={response.status_code}"
                )

                content_type_header = str(
                    response.headers.get("content-type", "")
                ).lower()

                # --- Handle API Success or Error from Response Body ---
                if response.status_code == 200 and content_type_header.startswith(
                    "audio/"
                ):
                    audio_bytes = response.content
                    if not audio_bytes:
                        message = (
                            "API returned success status but response body was empty."
                        )
                        logger.warning(
                            f"Venice Audio API (Voice: {voice_model}) returned 200 OK but empty audio content."
                        )
                        return {
                            "error": True,
                            "error_type": "NoContentError",
                            "message": message,
                            "status_code": response.status_code,
                            "voice_model": voice_model,
                            "requested_format": final_response_format,
                        }

                    # --- Store Audio ---
                    file_extension = final_response_format
                    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
                    key = f"{self.category}/{voice_model}/{audio_hash}.{file_extension}"

                    size_limit = 1024 * 20  # 20Mb Size limit
                    stored_url = await store_file_bytes(
                        file_bytes=audio_bytes,
                        key=key,
                        file_type=FileType.AUDIO,
                        size_limit_bytes=size_limit,
                    )

                    if not stored_url:
                        message = "Failed to store audio: S3 storage is not configured."
                        logger.error(
                            f"Failed to store audio (Voice: {voice_model}): S3 storage is not configured."
                        )
                        return {
                            "error": True,
                            "error_type": "StorageConfigurationError",
                            "message": message,
                            "voice_model": voice_model,
                            "requested_format": final_response_format,
                        }

                    logger.info(
                        f"Venice TTS success: Voice='{voice_model}', Format='{final_response_format}', Stored='{stored_url}'"
                    )
                    # --- Return Success Dictionary ---
                    return {
                        "audio_url": stored_url,
                        "audio_bytes_sha256": audio_hash,
                        "content_type": content_type_header,
                        "voice_model": voice_model,
                        "tts_engine": tts_model_id,
                        "speed": speed if speed is not None else 1.0,
                        "response_format": final_response_format,
                        "input_text_length": len(input),
                        "error": False,
                        "status_code": response.status_code,
                    }
                else:
                    # Non-200 API response or non-audio content
                    error_details: Any = f"Raw error response text: {response.text}"
                    try:
                        parsed_details = response.json()
                        error_details = parsed_details
                    except json.JSONDecodeError:
                        pass  # Keep raw text if JSON parsing fails

                    message = "Venice Audio API returned a non-success status or unexpected content type."
                    logger.error(
                        f"Venice Audio API Error: Voice='{voice_model}', Format='{final_response_format}', Status={response.status_code}, Details: {error_details}"
                    )
                    return {
                        "error": True,
                        "error_type": "APIError",
                        "message": message,
                        "status_code": response.status_code,
                        "details": error_details,
                        "voice_model": voice_model,
                        "requested_format": final_response_format,
                    }

        except Exception as e:
            # Global exception handling for any uncaught error
            error_type = type(
                e
            ).__name__  # Gets the class name of the exception (e.g., 'TimeoutException', 'ToolException')
            message = f"An unexpected error occurred during audio generation for voice {voice_model}."
            details = str(e)  # The string representation of the exception

            # Log the error with full traceback for debugging
            logger.error(
                f"Venice Audio Tool Global Error ({error_type}): {message} | Details: {details}",
                exc_info=True,
            )

            return {
                "error": True,
                "error_type": error_type,  # e.g., "TimeoutException", "ToolException", "ClientError", "ValueError"
                "message": message,
                "details": details,
                "voice_model": voice_model,
                "requested_format": final_response_format,
            }
