"""Skill for retrieving a single post's full content."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.agent_post import get_agent_post
from intentkit.core.system_skills.base import SystemSkill


class GetPostInput(BaseModel):
    """Input schema for getting a post by ID."""

    post_id: str = Field(..., description="The ID of the post to retrieve")


class GetPostSkill(SystemSkill):
    """Skill for retrieving a single post's full content by ID."""

    name: str = "get_post"
    description: str = "Get the full content of a post by its ID."
    args_schema: ArgsSchema | None = GetPostInput

    @override
    async def _arun(self, post_id: str) -> str:
        try:
            post = await get_agent_post(post_id)

            if post is None:
                return f"Post with ID '{post_id}' not found."

            result_lines = [
                f"Post (ID: {post.id})",
                f"Title: {post.title}",
                f"Created: {post.created_at.isoformat()}",
            ]
            if post.slug:
                result_lines.append(f"Slug: {post.slug}")
            if post.excerpt:
                result_lines.append(f"Excerpt: {post.excerpt}")
            if post.tags:
                result_lines.append(f"Tags: {', '.join(post.tags)}")
            if post.cover:
                result_lines.append(f"Cover: {post.cover}")
            result_lines.append(f"\n{post.markdown}")

            return "\n".join(result_lines)
        except ToolException:
            raise
        except Exception as e:
            self.logger.error(f"get_post failed: {e}", exc_info=True)
            raise ToolException(f"Failed to retrieve post: {e}") from e
