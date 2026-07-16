"""Tool for creating agent posts."""

from typing import Literal, cast, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.agent_post import create_agent_post
from intentkit.core.system_tools.base import SystemTool
from intentkit.models.agent_activity import AgentActivityCreate
from intentkit.models.agent_post import SLUG_MAX_LENGTH, AgentPostCreate
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType


class CreatePostInput(BaseModel):
    """Input schema for creating an agent post."""

    title: str = Field(..., description="Post title", max_length=200)
    markdown: str = Field(
        ...,
        description="Post body in markdown. Omit h1 title; use h2 for sections.",
    )
    # No max_length here: LLMs occasionally overshoot, and a hard schema
    # rejection wastes a whole turn. Longer slugs are truncated in _arun.
    slug: str = Field(
        ...,
        description=(
            "Unique URL slug (letters, digits, hyphens), "
            f"max {SLUG_MAX_LENGTH} characters"
        ),
        pattern="^[a-zA-Z0-9-]+$",
    )
    excerpt: str = Field(
        ..., description="Short summary, max 200 chars", max_length=200
    )
    tags: list[str] = Field(..., description="Tags, max 3", max_length=3)
    cover: str | None = Field(
        default=None, description="Cover image URL", max_length=1000
    )


def _truncate_slug(slug: str) -> str:
    """Cut an overlong slug to SLUG_MAX_LENGTH, preferring a hyphen boundary
    so no half word is left dangling. Slugs within the limit pass through."""
    if len(slug) <= SLUG_MAX_LENGTH:
        return slug
    truncated = slug[:SLUG_MAX_LENGTH]
    head = truncated.rpartition("-")[0].rstrip("-")
    # Back up to the hyphen boundary only when it keeps a reasonable share
    # of the budget ("a-bbb..." must not collapse to "a"), and never return
    # an empty slug (the model layer requires at least one character).
    if len(head) >= SLUG_MAX_LENGTH // 2:
        return head
    return truncated.rstrip("-") or truncated


class CreatePostTool(SystemTool):
    """Tool for creating a new agent post.

    This tool allows an agent to create a post with a title,
    markdown content, and optional cover image.
    """

    name: str = "create_post"
    team_only: bool = True
    description: str = (
        "Create a post with title, markdown body, and optional cover image."
    )
    args_schema: ArgsSchema | None = CreatePostInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    @override
    async def _arun(
        self,
        title: str,
        markdown: str,
        slug: str,
        excerpt: str,
        tags: list[str],
        cover: str | None = None,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Create a new agent post.

        Args:
            title: Title of the post.
            markdown: Content of the post in markdown format.
            slug: URL slug for the post.
            excerpt: Short excerpt of the post.
            tags: List of tags.
            cover: Optional URL of the cover image.

        Returns:
            A tuple of (message, attachments) with a card linking to the post.
        """

        try:
            self.ensure_own_team()
            context = self.get_context()
            agent_id = context.agent_id

            slug = _truncate_slug(slug)

            post_create = AgentPostCreate(
                agent_id=agent_id,
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
                text=f"Published a new post: {title}",
                post_id=post.id,
            )
            _ = await create_agent_activity(activity_create)

            # Build card attachment
            from intentkit.config.config import config

            post_url = f"{config.app_base_url}/post/{post.id}"

            attachment: ChatMessageAttachment = {
                "type": ChatMessageAttachmentType.CARD,
                "lead_text": None,
                "url": post_url,
                "json": cast(
                    dict[str, object],
                    {
                        "title": title,
                        "description": excerpt,
                        "label": "Read Post",
                        "image_url": cover,
                    },
                ),
            }

            content = (
                f"Post created successfully (ID: {post.id}). "
                f"A card with a link to the post has already been sent to the user. "
                f"Do NOT call ui_show_card again for this post, "
                f"and do NOT summarize the post content to the user."
            )

            return content, [attachment]
        except ToolException:
            raise
        except Exception as e:
            self.logger.error("create_post failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to create post: {e}") from e
