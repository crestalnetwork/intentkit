import logging
from typing import Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.cookiefun.base import CookieFunBaseTool

logger = logging.getLogger(__name__)


class GetAIResponseInput(BaseModel):
    """Input for GetAIResponse tool."""

    prompt: str = Field(description="The message/prompt to send to the Cookie.fun AI")


class GetAIResponse(CookieFunBaseTool):
    """Tool for interacting with Cookie.fun's AI chat."""

    name: str = "cookiefun_get_ai_response"
    description: str = (
        "Get a response from Cookie.fun's AI chat system.\n"
        "Use this when you need to interact with Cookie.fun's AI assistant."
    )
    args_schema: Type[BaseModel] = GetAIResponseInput

    async def _arun(self, prompt: str, config: RunnableConfig = None, **kwargs) -> str:
        """Get AI response from Cookie.fun API."""
        context = self.context_from_config(config)
        api_key = context.config.get("api_key")
        if not api_key:
            return "Error: Cookie.fun API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.cookie-api.com/api/ai/message",
                    params={"prompt": prompt},
                    headers={"Authorization": api_key},
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    return data.get("answer", "No response received")
                else:
                    return f"Error: {data.get('error', 'Unknown error')}"

        except httpx.HTTPError as e:
            logger.error(f"HTTP error when getting AI response: {str(e)}")
            return f"Error fetching AI response: {str(e)}"
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return f"Unexpected error: {str(e)}"
