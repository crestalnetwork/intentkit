"""Skill for reading webpage content as markdown via Cloudflare Browser Rendering."""

import logging
import re
from typing import Annotated, override

import httpx
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill

logger = logging.getLogger(__name__)

CLEAN_CONTENT_PROMPT = """\
You are a content extractor. Given raw markdown converted from a webpage, \
extract only the meaningful, readable content. Remove:
- Navigation menus, headers, footers, sidebars
- Cookie notices, ads, promotional banners
- Repetitive links, social media buttons
- Any boilerplate or non-content elements

Return ONLY the clean, readable main content in markdown format. \
Do not add any commentary or explanation."""


class ReadWebpageInput(BaseModel):
    """Input schema for reading a webpage."""

    url: str = Field(..., description="The URL of the webpage to read")


class ReadWebpageSkill(SystemSkill):
    """Skill for reading webpage content as markdown.

    Uses Cloudflare Browser Rendering REST API to fetch and convert
    webpages to markdown format, then cleans the content with an LLM.
    """

    name: str = "read_webpage"
    description: str = (
        "Read a webpage and return its content as markdown. "
        "Useful when you need to read and understand the content of a specific URL."
    )
    args_schema: ArgsSchema | None = ReadWebpageInput

    @override
    async def _arun(
        self,
        url: str,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
    ) -> str:
        """Read a webpage and return its content as markdown.

        Args:
            url: The URL of the webpage to read.
            tool_call_id: Injected by LangChain runtime.

        Returns:
            The webpage content converted to markdown.
        """
        try:
            from intentkit.config.config import config

            account_id = config.cloudflare_account_id
            api_token = config.cloudflare_api_token
            if not account_id or not api_token:
                raise ToolException(
                    "Cloudflare Browser Rendering is not configured. "
                    "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
                )

            # Fetch webpage as markdown via Cloudflare
            raw_markdown = await self._fetch_markdown(account_id, api_token, url)
            if not raw_markdown:
                return "The webpage returned no content."

            # Clean whitespace: collapse multiple spaces into one
            cleaned = re.sub(r" {2,}", " ", raw_markdown)
            # Also collapse 3+ consecutive newlines into 2
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

            # Clean content with LLM
            cleaned = await self._clean_with_llm(cleaned, tool_call_id)

            # Truncate very long content
            max_chars = 50000
            if len(cleaned) > max_chars:
                cleaned = cleaned[:max_chars] + "\n\n... (content truncated)"

            return cleaned

        except ToolException:
            raise
        except Exception as e:
            logger.error("read_webpage failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to read webpage: {e}") from e

    async def _fetch_markdown(self, account_id: str, api_token: str, url: str) -> str:
        """Fetch a URL and convert to markdown via Cloudflare Browser Rendering."""
        api_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/markdown"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                api_url,
                json={
                    "url": url,
                    "rejectRequestPattern": [".*\\.(css|ico|svg|woff2?|ttf|eot)$"],
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}",
                },
            )

        if response.status_code != 200:
            raise ToolException(
                f"Cloudflare API returned status {response.status_code}: {response.text}"
            )

        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            raise ToolException(f"Cloudflare API error: {errors}")

        return data.get("result", "")

    async def _clean_with_llm(self, content: str, tool_call_id: str | None) -> str:
        """Use a long-context LLM to extract readable content from raw markdown."""
        from intentkit.models.llm import create_llm_model
        from intentkit.models.llm_picker import pick_long_context_model

        model_id = pick_long_context_model()
        llm_model = await create_llm_model(model_id, temperature=0)
        llm = await llm_model.create_instance()

        response = await llm.ainvoke(
            [
                {"role": "system", "content": CLEAN_CONTENT_PROMPT},
                {"role": "user", "content": content},
            ]
        )

        # Bill for the LLM usage
        input_tokens = (
            response.usage_metadata.get("input_tokens", 0)
            if response.usage_metadata
            else 0
        )
        output_tokens = (
            response.usage_metadata.get("output_tokens", 0)
            if response.usage_metadata
            else 0
        )
        cached_input_tokens = (
            response.usage_metadata.get("input_token_details", {}).get("cache_read", 0)
            if response.usage_metadata
            else 0
        )

        try:
            context = self.get_context()
            payer = context.payer
            if payer and tool_call_id:
                from intentkit.core.credit.expense import expense_skill_internal_llm

                await expense_skill_internal_llm(
                    user_id=payer,
                    agent=context.agent,
                    skill_name=self.name,
                    skill_call_id=tool_call_id,
                    start_message_id=context.start_message_id,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                )
        except Exception as e:
            logger.warning("Failed to bill for LLM cleaning: %s", e)

        result = response.content
        return str(result) if result else content
