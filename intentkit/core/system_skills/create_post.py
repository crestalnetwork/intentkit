"""Skill for creating agent posts."""

from typing import Any

from pydantic import BaseModel, Field

from intentkit.core.agent_post import create_agent_post
from intentkit.models.agent_post import AgentPostCreate
from intentkit.skills.base import IntentKitSkill


class CreatePostInput(BaseModel):
    """Input schema for creating an agent post."""

    title: str = Field(
        ...,
        description="Title of the post",
        max_length=200,
    )
    markdown: str = Field(
        ...,
        description="Content of the post in markdown format",
    )
    cover: str | None = Field(
        default=None,
        description="URL of the cover image",
        max_length=1000,
    )


class CreatePostSkill(IntentKitSkill):
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
    args_schema: type[BaseModel] = CreatePostInput

    @property
    def category(self) -> str:
        """Get the category of the skill."""
        return "system"

    async def _arun(
        self,
        title: str,
        markdown: str,
        cover: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Create a new agent post.

        Args:
            title: Title of the post. 
            markdown: Content of the post in markdown format.
            cover: Optional URL of the cover image. 

        Returns:
            A message indicating success with the post ID.
        """
        context = self.get_context()
        agent_id = context.agent_id

        post_create = AgentPostCreate(
            agent_id=agent_id,
            title=title,
            markdown=markdown,
            cover=cover,
        )

        post = await create_agent_post(post_create)

        return f"Post created successfully with ID: {post.id}"