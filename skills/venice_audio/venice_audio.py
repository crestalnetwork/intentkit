# File: skills/venice_audio/venice_audio_tool.py (Example path)

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Type

import httpx

# Ensure these are installed: pip install boto3 botocore filetype
from botocore.exceptions import ClientError
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

# Import necessary base classes and utilities
from abstracts.skill import SkillStoreABC
from skills.venice_audio.base import VeniceAudioBaseTool
from skills.venice_audio.input import AllowedAudioFormat, VeniceAudioInput
from utils.s3 import FileType, store_file_bytes

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
    Network errors or internal processing errors will still raise exceptions.
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
    voice_model: str = Field(
        description="REQUIRED identifier for the specific Venice AI voice model to use for TTS generation (e.g., 'af_sky', 'am_echo'). This must be set per tool instance."
    )

    # --- Core Execution Method ---
    async def _arun(
        self,
        input: str,
        speed: Optional[float] = 1.0,
        response_format: Optional[AllowedAudioFormat] = "mp3",
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates audio using the configured voice model via Venice AI TTS /audio/speech endpoint.
        Stores the resulting audio using store_file_bytes.
        Returns a dictionary containing audio details on success, or API error details on failure.
        """
        context = self.context_from_config(config)

        try:
            # --- Setup ---
            api_key = self.get_api_key(context)
            if not api_key:
                logger.error(
                    f"Venice AI API key configuration missing for skill '{self.name}'."
                )
                # This is a setup error, not an API error, so raise it.
                raise ValueError(
                    f"Venice AI API key not found for category '{self.category}'. Please configure it."
                )

            # Apply rate limiting (can raise ConnectionAbortedError)
            await self.apply_rate_limit(context)

        except (ValueError, ConnectionAbortedError) as setup_err:
            # Let setup errors propagate immediately
            raise setup_err

        # --- Prepare API Call ---
        final_response_format = response_format if response_format else "mp3"
        tts_model_id = "tts-kokoro"  # API model used

        # Ensure voice_model is set on the instance
        if not self.voice_model:
            logger.error(
                f"Instance of {self.name} was created without a 'voice_model'."
            )
            raise ValueError("Voice model must be specified for this tool instance.")

        payload = {
            "model": tts_model_id,
            "input": input,
            "voice": self.voice_model,  # Use the instance's voice model
            "response_format": final_response_format,
            "speed": speed if speed is not None else 1.0,
            "streaming": False,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        logger.debug(
            f"Venice Audio API Call: Voice='{self.voice_model}', Format='{final_response_format}', Payload='{payload}'"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        api_url = f"{base_url}/api/v1/audio/speech"

        try:
            # --- Execute API Call ---
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                logger.debug(
                    f"Venice Audio API Response: Voice='{self.voice_model}', Format='{final_response_format}', Status={response.status_code}"
                )

                content_type_header = str(
                    response.headers.get("content-type", "")
                ).lower()

                # --- Handle Success (200 OK with audio content) ---
                if response.status_code == 200 and content_type_header.startswith(
                    "audio/"
                ):
                    audio_bytes = response.content
                    if not audio_bytes:
                        logger.warning(
                            f"Venice Audio API (Voice: {self.voice_model}) returned 200 OK but empty audio content."
                        )
                        # Return as error, as no audio was actually received
                        return {
                            "error": True,
                            "status_code": response.status_code,
                            "details": "API returned success status but response body was empty.",
                            "voice_model": self.voice_model,
                            "requested_format": final_response_format,
                        }

                    # --- Store Audio ---
                    try:
                        file_extension = final_response_format
                        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
                        # Key: category / voice / hash . extension
                        key = f"{self.category}/{self.voice_model}/{audio_hash}.{file_extension}"

                        size_limit = 1024 * 1024 * 20  # 20Mb Size limit
                        stored_url = await store_file_bytes(
                            file_bytes=audio_bytes,
                            key=key,
                            file_type=FileType.AUDIO,
                            size_limit_bytes=size_limit,
                        )

                        # If S3 is not configured, store_file_bytes returns "" - treat as error
                        if not stored_url:
                            logger.error(
                                f"Failed to store audio (Voice: {self.voice_model}): S3 storage is not configured."
                            )
                            # Raise internal error, as storage failed post-API success
                            raise ValueError(
                                "S3 storage is not configured, cannot save the generated audio."
                            )

                        logger.info(
                            f"Venice TTS success: Voice='{self.voice_model}', Format='{final_response_format}', Stored='{stored_url}'"
                        )
                        # --- Return Success Dictionary ---
                        return {
                            "audio_url": stored_url,
                            "audio_bytes_sha256": audio_hash,
                            "content_type": content_type_header,  # Actual content type from response
                            "voice_model": self.voice_model,
                            "tts_engine": tts_model_id,
                            "speed": speed if speed is not None else 1.0,
                            "response_format": final_response_format,
                            "input_text_length": len(input),
                            "error": False,  # Explicitly indicate success
                            "status_code": response.status_code,
                        }
                    except (ValueError, ClientError) as storage_err:
                        # Errors during storage (size limit, S3 issues) should raise
                        logger.error(
                            f"Failed to store audio file (Voice: {self.voice_model}): {storage_err}",
                            exc_info=True,
                        )
                        raise Exception(
                            f"Failed to store generated audio: {storage_err}"
                        ) from storage_err

                # --- Handle API Errors (Non-200 Status) ---
                else:
                    error_message = f"Venice Audio API Error: Voice='{self.voice_model}', Format='{final_response_format}', Status={response.status_code}"
                    error_details: Any = (
                        f"Raw error response text: {response.text}"  # Default detail
                    )
                    try:
                        # Attempt to parse JSON for structured details
                        parsed_details = response.json()
                        error_details = parsed_details  # Use parsed JSON if successful
                        error_message += f", Details: {json.dumps(error_details)}"
                    except json.JSONDecodeError:
                        # Keep raw text if JSON parsing fails
                        error_message += f", Raw Body: {response.text}"
                    except Exception as parse_err:
                        logger.error(
                            f"Failed to parse error response body: {parse_err}",
                            exc_info=True,
                        )
                        # Keep raw text as fallback

                    logger.error(error_message)  # Log detailed error

                    # --- Return Error Dictionary ---
                    return {
                        "error": True,
                        "status_code": response.status_code,
                        "details": error_details,  # Contains parsed JSON or raw text
                        "voice_model": self.voice_model,
                        "requested_format": final_response_format,
                    }

        # --- Handle Network/Connection Errors ---
        except httpx.TimeoutException as e:
            logger.error(
                f"Network Error: Venice Audio API (Voice: {self.voice_model}) request timed out: {e}"
            )
            # Re-raise as standard TimeoutError
            raise TimeoutError(
                f"Request to Venice AI Audio timed out (Voice: {self.voice_model})."
            ) from e
        except httpx.RequestError as e:
            logger.error(
                f"Network Error: Venice Audio API (Voice: {self.voice_model}) request error: {e}"
            )
            # Re-raise as standard ConnectionError
            raise ConnectionError(
                f"Could not connect to Venice Audio API (Voice: {self.voice_model}): {str(e)}"
            ) from e

        # --- Handle Unexpected Errors ---
        except Exception as e:
            # Catch any other unexpected error during the process
            logger.error(
                f"Unexpected Error during Venice audio generation (Voice: {self.voice_model}): {e}",
                exc_info=True,
            )
            # Re-raise wrapped in a generic Exception
            raise Exception(
                f"An unexpected error occurred processing audio request for voice {self.voice_model}."
            ) from e
