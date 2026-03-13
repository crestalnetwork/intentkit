"""Skill for creating agent activities."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.agent import get_agent
from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.system_skills.base import SystemSkill
from intentkit.models.agent_activity import AgentActivityCreate


class CreateActivityInput(BaseModel):
    """Input schema for creating an agent activity."""

    text: str = Field(..., description="Activity content")
    images: list[str] | None = Field(default=None, description="Image URLs")
    video: str | None = Field(default=None, description="Video URL")
    post_id: str | None = Field(default=None, description="Related post ID")


class CreateActivitySkill(SystemSkill):
    """Skill for creating a new agent activity.

    This skill allows an agent to create an activity with text content,
    optional images, video, and a reference to a related post.
    """

    name: str = "create_activity"
    description: str = (
        "Publish an activity to your public timeline. "
        "IMPORTANT: Only use this skill when the user EXPLICITLY asks you to create, publish, or post an activity. "
        "Do NOT call this on your own initiative, even to log or summarize what you did."
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
        try:
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
        except ToolException:
            raise
        except Exception as e:
            self.logger.error(f"create_activity failed: {e}", exc_info=True)
            raise ToolException(f"Failed to create activity: {e}") from e
