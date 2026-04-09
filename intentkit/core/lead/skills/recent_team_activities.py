"""Skill to read the team's recent activity feed."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException

from intentkit.core.lead.skills.base import LeadSkill
from intentkit.skills.base import NoArgsSchema


class LeadRecentTeamActivities(LeadSkill):
    """Skill to retrieve the team's recent activities from all subscribed agents."""

    name: str = "lead_recent_team_activities"
    description: str = (
        "Retrieve the team's 20 most recent activities from all subscribed agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> str:
        from intentkit.core.team.feed import query_activity_feed

        context = self.get_context()
        team_id = context.team_id
        if not team_id:
            raise ToolException("No team_id in context")

        activities, _ = await query_activity_feed(team_id, limit=20)

        if not activities:
            return "No recent activities found in the team feed."

        result_lines = [f"Found {len(activities)} recent team activities:"]
        for i, activity in enumerate(activities, 1):
            result_lines.append(f"\n--- Activity {i} (ID: {activity.id}) ---")
            result_lines.append(f"Agent: {activity.agent_name or activity.agent_id}")
            result_lines.append(f"Created: {activity.created_at.isoformat()}")
            result_lines.append(f"Text: {activity.text}")
            if activity.images:
                result_lines.append(f"Images: {', '.join(activity.images)}")
            if activity.video:
                result_lines.append(f"Video: {activity.video}")
            if activity.link:
                result_lines.append(f"Link: {activity.link}")
            if activity.post_id:
                result_lines.append(f"Related Post ID: {activity.post_id}")

        return "\n".join(result_lines)


lead_recent_team_activities_skill = LeadRecentTeamActivities()
