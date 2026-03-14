"""Skill for creating agent activities."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field, field_validator

from intentkit.core.agent import get_agent
from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.system_skills.base import SystemSkill
from intentkit.models.agent_activity import AgentActivityCreate
from intentkit.utils.opengraph import fetch_link_meta


class CreateActivityInput(BaseModel):
    """Input schema for creating an agent activity."""

    text: str = Field(..., description="Activity content, plain text, max 280 bytes")
    images: list[str] | None = Field(
        default=None, max_length=4, description="Image URLs"
    )

    @field_validator("text")
    @classmethod
    def text_max_280_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 280:
            raise ValueError("text must be at most 280 bytes")
        return v

    video: str | None = Field(default=None, description="Video URL")
    link: str | None = Field(default=None, description="URL to share")

    @field_validator("link")
    @classmethod
    def link_must_be_http(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("link must start with http:// or https://")
        return v


class CreateActivitySkill(SystemSkill):
    """Skill for creating a new agent activity."""

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
        link: str | None = None,
    ) -> str:
        """Create a new agent activity.

        Args:
            text: Content of the activity.
            images: Optional list of image URLs.
            video: Optional video URL.
            link: Optional URL to share.

        Returns:
            A message indicating success with the activity ID.
        """
        try:
            context = self.get_context()
            agent_id = context.agent_id

            agent = await get_agent(agent_id)
            agent_name = agent.name if agent else None
            agent_picture = agent.picture if agent else None

            link_meta = None
            if link:
                meta = await fetch_link_meta(link)
                if meta:
                    link_meta = meta.model_dump()

            activity_create = AgentActivityCreate(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_picture=agent_picture,
                text=text,
                images=images,
                video=video,
                link=link,
                link_meta=link_meta,
            )

            activity = await create_agent_activity(activity_create)

            return f"Activity created successfully with ID: {activity.id}"
        except ToolException:
            raise
        except Exception as e:
            self.logger.error(f"create_activity failed: {e}", exc_info=True)
            raise ToolException(f"Failed to create activity: {e}") from e
