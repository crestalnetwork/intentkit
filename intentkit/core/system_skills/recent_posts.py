"""Skill for retrieving agent's recent posts."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException

from intentkit.core.agent_post import get_agent_posts
from intentkit.core.system_skills.base import SystemSkill
from intentkit.skills.base import NoArgsSchema


class RecentPostsSkill(SystemSkill):
    """Skill for retrieving the agent's recent posts.

    Returns a list of posts with excerpts (no full markdown) to save context.
    """

    name: str = "recent_posts"
    description: str = "Retrieve your 10 most recent posts (titles and excerpts only, no full content)."
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self) -> str:
        try:
            context = self.get_context()
            agent_id = context.agent_id

            posts = await get_agent_posts(agent_id, limit=10)

            if not posts:
                return "No recent posts found."

            result_lines = [f"Found {len(posts)} recent posts:"]
            for i, post in enumerate(posts, 1):
                result_lines.append(f"\n--- Post {i} (ID: {post.id}) ---")
                result_lines.append(f"Title: {post.title}")
                result_lines.append(f"Created: {post.created_at.isoformat()}")
                if post.slug:
                    result_lines.append(f"Slug: {post.slug}")
                if post.excerpt:
                    result_lines.append(f"Excerpt: {post.excerpt}")
                if post.tags:
                    result_lines.append(f"Tags: {', '.join(post.tags)}")
                if post.cover:
                    result_lines.append(f"Cover: {post.cover}")

            return "\n".join(result_lines)
        except ToolException:
            raise
        except Exception as e:
            self.logger.error("recent_posts failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to retrieve recent posts: {e}") from e
