"""Skill for creating agent posts."""

from typing import cast, override

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.agent_post import create_agent_post
from intentkit.models.agent_activity import AgentActivityCreate
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
    slug: str = Field(
        ...,
        description="URL slug for the post. Must be unique within the agent.",
        max_length=60,
        pattern="^[a-zA-Z0-9-]+$",
    )
    excerpt: str = Field(
        ...,
        description="Short excerpt of the post. Max 200 characters.",
        max_length=200,
    )
    tags: list[str] = Field(
        ...,
        description="List of tags. Max 3 tags.",
        max_length=3,
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
        slug: str,
        excerpt: str,
        tags: list[str],
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
        slug: str,
        excerpt: str,
        tags: list[str],
        cover: str | None = None,
    ) -> str:
        """Create a new agent post.

        Args:
            title: Title of the post.
            markdown: Content of the post in markdown format.
            slug: URL slug for the post.
            excerpt: Short excerpt of the post.
            tags: List of tags.
            cover: Optional URL of the cover image.

        Returns:
            A message indicating success with the post ID.
        """

        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ToolException("No AgentContext found")
        agent_id = context.agent_id

        from intentkit.core.agent import get_agent

        agent = await get_agent(agent_id)
        if agent is None:
            raise ToolException(f"Agent with ID {agent_id} not found")

        agent_name = agent.name or "Unknown Agent"
        agent_picture = agent.picture

        post_create = AgentPostCreate(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_picture=agent_picture,
            title=title,
            markdown=markdown,
            cover=cover,
            slug=slug,
            excerpt=excerpt,
            tags=tags,
        )

        post = await create_agent_post(post_create)

        activity_create = AgentActivityCreate(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_picture=agent_picture,
            text=f"Published a new post: {title}",
            post_id=post.id,
        )
        await create_agent_activity(activity_create)

        return f"Post created successfully with ID: {post.id}"
