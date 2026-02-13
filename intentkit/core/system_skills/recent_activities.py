"""Skill for retrieving agent's recent activities."""

from typing import override

from langchain_core.tools import ArgsSchema

from intentkit.core.agent_activity import get_agent_activities
from intentkit.core.system_skills.base import SystemSkill
from intentkit.skills.base import NoArgsSchema


class RecentActivitiesSkill(SystemSkill):
    """Skill for retrieving the agent's recent activities.

    This skill allows an agent to retrieve its own recent activities,
    helping it understand what actions it has taken recently.
    """

    name: str = "recent_activities"
    description: str = (
        "Retrieve your 10 most recent activities to understand what you have done recently. "
        "Use this to review your past actions and maintain context of your work."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self) -> str:
        """Retrieve the agent's recent activities.

        Returns:
            A formatted string containing the agent's 10 most recent activities.
        """
        context = self.get_context()
        agent_id = context.agent_id

        activities = await get_agent_activities(agent_id, limit=10)

        if not activities:
            return "No recent activities found."

        # Format activities into a readable string
        result_lines = [f"Found {len(activities)} recent activities:"]
        for i, activity in enumerate(activities, 1):
            result_lines.append(f"\n--- Activity {i} (ID: {activity.id}) ---")
            result_lines.append(f"Created: {activity.created_at.isoformat()}")
            result_lines.append(f"Text: {activity.text}")
            if activity.images:
                result_lines.append(f"Images: {', '.join(activity.images)}")
            if activity.video:
                result_lines.append(f"Video: {activity.video}")
            if activity.post_id:
                result_lines.append(f"Related Post ID: {activity.post_id}")

        return "\n".join(result_lines)
