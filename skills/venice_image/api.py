"""
This module encapsulates all interactions with the Venice AI API.
It provides a function, make_venice_api_request, to make POST requests
to the API and handles the responses, including error handling,
content type checking, and image storage via S3.  This separation
of concerns keeps the core skill logic cleaner and easier to maintain.
"""

import hashlib
import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)


async def make_venice_api_request(
    api_key: str,
    path: str,
    payload: Dict[str, Any],
    category: str,
    tool_name: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Makes a POST request to the Venice AI API, handling all aspects
    of the API interaction.  This includes:

    1.  Constructing the API URL using a base URL and the provided path.
    2.  Adding the required authorization header with the provided API key.
    3.  Sending the POST request with the given payload.
    4.  Handling potential connection and HTTP errors.
    5.  Calling the internal _handle_response function to process the API's
        response, which might be JSON or an image.

    Args:
        api_key: The Venice AI API key for authentication.
        path: The API endpoint path (e.g., "/api/v1/image/generate").  Should *not* start with the base URL.
        payload: The data to send in the request body (as JSON).
        category: The category of the skill making the request (e.g., "venice_image"). Used for S3 storage and logging purpose.
        tool_name: The name of the tool or skill making the request (e.g., "image_generation"). Used for S3 storage and logging purpose.

    Returns:
        A tuple: (success_data, error_data).
        - success_data:  A dictionary containing the parsed JSON response from the API if the request was successful
          (or a dictionary containing the S3 URL if the response is an image).
        - error_data:  A dictionary containing information about any errors that occurred,
          or None if the request was successful.  The dictionary includes an 'error' key.
    """

    venice_base_url = "https://api.venice.ai"  # Venice AI API base URL

    if not path.startswith("/"):
        path = "/" + path

    api_url = f"{venice_base_url}{path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "image/*, application/json",
    }

    logger.info(
        f"[{category}/{tool_name}] Sending request to {api_url} with payload: {payload}"
    )

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            return await _handle_response(response, category, tool_name)

    except httpx.RequestError as e:
        error_msg = f"Connection error: {e}"
        logger.error(f"[{category}/{tool_name}] {error_msg}")
        return {}, {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"[{category}/{tool_name}] {error_msg}", exc_info=True)
        return {}, {"success": False, "error": error_msg}


async def _handle_response(
    response: httpx.Response, category: str, tool_name: str
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Handles the API response, differentiating between JSON and image responses.

    If the response is an image (based on the 'content-type' header),
    it stores the image in S3 and returns the S3 URL.
    If the response is JSON, it parses the JSON and returns it.
    If any errors occur, it returns an error dictionary.
    """

    content_type = str(response.headers.get("content-type", "")).lower()

    if response.status_code == 200 and content_type.startswith("image/"):
        try:
            upscaled_image_bytes = response.content
            image_hash = hashlib.sha256(upscaled_image_bytes).hexdigest()
            file_extension = content_type.split("/")[-1].split("+")[0] or "png"

            key = f"{category}/{tool_name}/{image_hash}.{file_extension}"

            logger.info(f"[{category}/{tool_name}] Storing image with key: {key}")

            stored_url = await store_image_bytes(
                upscaled_image_bytes, key, content_type=content_type
            )

            return {"success": True, "result": stored_url}, None

        except Exception as e:
            error_msg = f"Error processing image response: {e}"
            logger.error(f"[{category}/{tool_name}] {error_msg}", exc_info=True)
            return {}, {"success": False, "error": error_msg}

    elif response.status_code == 200:
        try:
            logger.info(f"[{category}/{tool_name}] Received successful JSON response.")
            return response.json(), None
        except Exception as json_err:
            error_msg = f"Failed to parse JSON response: {json_err} - {response.text}"
            logger.error(f"[{category}/{tool_name}] {error_msg}")
            return {}, {"success": False, "error": error_msg}

    else:
        try:
            error_data = response.json()
            error_msg = f"API returned error: {error_data.get('message', error_data.get('detail', response.text))}"
            logger.error(f"[{category}/{tool_name}] {error_msg}")
            return {}, {"success": False, "error": error_msg}
        except Exception:
            error_msg = f"API returned status code {response.status_code} with text: {response.text}"
            logger.error(f"[{category}/{tool_name}] {error_msg}")
            return {}, {"success": False, "error": error_msg}
