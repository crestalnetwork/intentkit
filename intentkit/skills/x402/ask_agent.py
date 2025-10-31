import logging
from typing import Any

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.config.config import config
from intentkit.models.chat import AuthorType
from intentkit.skills.x402.base import X402BaseSkill

logger = logging.getLogger(__name__)


class AskAgentInput(BaseModel):
    """Arguments for the x402 ask agent skill."""

    agent_id: str = Field(description="ID or slug of the agent to query.")
    message: str = Field(description="Message to send to the target agent.")
    search_mode: bool | None = Field(
        default=None, description="Enable search mode when interacting with the agent."
    )
    super_mode: bool | None = Field(
        default=None, description="Enable super mode when interacting with the agent."
    )


class X402AskAgent(X402BaseSkill):
    """Skill that queries another agent via the x402 API."""

    name: str = "x402_ask_agent"
    description: str = (
        "Call another agent through the x402 API and return the final agent message."
    )
    args_schema: type[BaseModel] = AskAgentInput

    async def _arun(
        self,
        agent_id: str,
        message: str,
        search_mode: bool | None = None,
        super_mode: bool | None = None,
    ) -> str:
        try:
            # Use wallet provider signer to satisfy eth_account.BaseAccount interface requirements
            base_url = (config.open_api_base_url or "").rstrip("/")
            if not base_url:
                raise ToolException("X402 API base URL is not configured.")
            target_url = f"{base_url}/x402"
            payload: dict[str, Any] = {
                "agent_id": agent_id,
                "message": message,
                "app_id": "skill",
            }
            if search_mode is not None:
                payload["search_mode"] = search_mode
            if super_mode is not None:
                payload["super_mode"] = super_mode

            async with self.http_client(timeout=20.0) as client:
                response = await client.post(target_url, json=payload)
                try:
                    response.raise_for_status()
                except Exception as e:
                    error_body = ""
                    try:
                        error_body = response.text
                    except Exception:
                        error_body = "Unable to read response body"
                    logger.error(
                        f"HTTP request failed with status {response.status_code}: {error_body}"
                    )
                    raise ToolException(
                        f"HTTP request failed with status {response.status_code}: {error_body}"
                    ) from e
                messages = response.json()
            if not isinstance(messages, list) or not messages:
                raise ValueError("Agent returned an empty response.")

            last_message = messages[-1]
            if not isinstance(last_message, dict):
                raise ValueError("Agent response format is invalid.")

            author_type = last_message.get("author_type")
            content = last_message.get("message")

            if author_type == AuthorType.SYSTEM.value:
                raise ToolException(content or "Agent returned a system message.")

            if not content:
                raise ToolException("Agent response did not include message text.")

            return str(content)
        except ToolException:
            # Re-raise ToolException as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in x402_ask_agent: {str(e)}")
            raise ToolException(f"Unexpected error occurred: {str(e)}") from e
