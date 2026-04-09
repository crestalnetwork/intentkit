"""Skill to read the team's recent post feed."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.skills.base import NoArgsSchema


class LeadRecentTeamPosts(LeadSkill):
    """Skill to retrieve the team's recent posts from all subscribed agents."""

    name: str = "lead_recent_team_posts"
    description: str = (
        "Retrieve the team's 20 most recent posts (titles and excerpts, no full content). "
        "Use lead_get_post to read full content of a specific post."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> str:
        from intentkit.core.team.feed import query_post_feed

        context = self.get_context()
        team_id = context.team_id
        if not team_id:
            raise ToolException("No team_id in context")

        posts, _ = await query_post_feed(team_id, limit=20)

        if not posts:
            return "No recent posts found in the team feed."

        result_lines = [f"Found {len(posts)} recent team posts:"]
        for i, post in enumerate(posts, 1):
            result_lines.append(f"\n--- Post {i} (ID: {post.id}) ---")
            result_lines.append(f"Agent: {post.agent_name}")
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


lead_recent_team_posts_skill = LeadRecentTeamPosts()
