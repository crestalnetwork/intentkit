"""Skill for creating agent posts."""

import re
from typing import cast, override

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.core.agent_post import create_agent_post
from intentkit.models.agent_post import AgentPostCreate


class CreatePostInput(BaseModel):
    """Input schema for creating an agent post."""

    title: str = Field(
        ...,
        description="Title of the post",
        max_length=200,
    )
    markdown: str = Field(
        ...,
        description=(
            "Content of the post in markdown format. "
            "Do not include the title (h1) in the content, only the body text. "
            "Use h2 (##) for section headings."
        ),
    )
    cover: str | None = Field(
        default=None,
        description="URL of the cover image",
        max_length=1000,
    )


class CreatePostSkill(BaseTool):
    """Skill for creating a new agent post.

    This skill allows an agent to create a post with a title,
    markdown content, and optional cover image.
    """

    name: str = "create_post"
    description: str = (
        "Create a new post for the agent. Posts can include a title, "
        "markdown content, and an optional cover image URL. "
        "Use this to publish articles, announcements, or long-form content."
    )
    args_schema: type[BaseModel] = CreatePostInput  # pyright: ignore[reportIncompatibleVariableOverride]

    @override
    def _run(
        self,
        title: str,
        markdown: str,
        cover: str | None = None,
    ) -> str:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports asynchronous skill calls"
        )

    @override
    async def _arun(
        self,
        title: str,
        markdown: str,
        cover: str | None = None,
    ) -> str:
        """Create a new agent post.

        Args:
            title: Title of the post.
            markdown: Content of the post in markdown format.
            cover: Optional URL of the cover image.

        Returns:
            A message indicating success with the post ID.
        """
        # Check if markdown contains h1 headings (lines starting with single #)
        # Match lines that start with # followed by a space (but not ## or more)
        if re.search(r"^#\s", markdown, re.MULTILINE):
            raise ToolException(
                (
                    "Markdown content should not include h1 headings (# title). "
                    "The title is provided separately. Use h2 (##) for section headings."
                )
            )

        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ToolException("No AgentContext found")
        agent_id = context.agent_id

        post_create = AgentPostCreate(
            agent_id=agent_id,
            title=title,
            markdown=markdown,
            cover=cover,
        )

        post = await create_agent_post(post_create)

        return f"Post created successfully with ID: {post.id}"
