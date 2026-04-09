"""Skill to retrieve a single post's full content for the lead agent."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.skills.base import LeadSkill


class LeadGetPostInput(BaseModel):
    """Input schema for getting a post by ID."""

    post_id: str = Field(..., description="The ID of the post to retrieve")


class LeadGetPost(LeadSkill):
    """Skill for retrieving a single post's full content by ID.

    This is a lead-specific wrapper that can read posts from any agent in the team.
    """

    name: str = "lead_get_post"
    description: str = "Get the full content of a post by its ID."
    args_schema: ArgsSchema | None = LeadGetPostInput

    @override
    async def _arun(self, post_id: str, **kwargs: Any) -> str:
        from intentkit.core.agent_post import get_agent_post
        from intentkit.core.lead.service import verify_agent_in_team

        context = self.get_context()

        post = await get_agent_post(post_id)

        if post is None:
            return f"Post with ID '{post_id}' not found."

        # Verify the post's agent belongs to this team
        if context.team_id:
            try:
                await verify_agent_in_team(post.agent_id, context.team_id)
            except Exception:
                return f"Post with ID '{post_id}' not found."

        result_lines = [
            f"Post (ID: {post.id})",
            f"Agent: {post.agent_name}",
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


lead_get_post_skill = LeadGetPost()
