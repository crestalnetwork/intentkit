"""Skill for creating agent activities."""

from typing import override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.agent import get_agent
from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.system_skills.base import SystemSkill
from intentkit.models.agent_activity import AgentActivityCreate


class CreateActivityInput(BaseModel):
    """Input schema for creating an agent activity."""

    text: str = Field(
        ...,
        description="Content of the activity",
    )
    images: list[str] | None = Field(
        default=None,
        description="List of image URLs to attach to the activity",
    )
    video: str | None = Field(
        default=None,
        description="Video URL to attach to the activity",
    )
    post_id: str | None = Field(
        default=None,
        description="ID of a related post, if this activity references a post",
    )


class CreateActivitySkill(SystemSkill):
    """Skill for creating a new agent activity.

    This skill allows an agent to create an activity with text content,
    optional images, video, and a reference to a related post.
    """

    name: str = "create_activity"
    description: str = (
        "Create a new activity for the agent. Activities can include text, "
        "images, video, and optionally reference a related post. "
        "Use this to share updates, media content, or announcements."
    )
    args_schema: ArgsSchema | None = CreateActivityInput

    @override
    async def _arun(
        self,
        text: str,
        images: list[str] | None = None,
        video: str | None = None,
        post_id: str | None = None,
    ) -> str:
        """Create a new agent activity.

        Args:
            text: Content of the activity.
            images: Optional list of image URLs.
            video: Optional video URL.
            post_id: Optional ID of a related post.

        Returns:
            A message indicating success with the activity ID.
        """
        context = self.get_context()
        agent_id = context.agent_id

        agent = await get_agent(agent_id)
        agent_name = agent.name if agent else None
        agent_picture = agent.picture if agent else None

        activity_create = AgentActivityCreate(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_picture=agent_picture,
            text=text,
            images=images,
            video=video,
            post_id=post_id,
        )

        activity = await create_agent_activity(activity_create)

        return f"Activity created successfully with ID: {activity.id}"
