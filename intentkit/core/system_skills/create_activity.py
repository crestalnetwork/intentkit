"""Skill for creating agent activities."""

from typing import cast, override

from langchain_core.tools import BaseTool
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.core.agent import get_agent
from intentkit.core.agent_activity import create_agent_activity
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


class CreateActivitySkill(BaseTool):
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
    args_schema: type[BaseModel] = CreateActivityInput  # pyright: ignore[reportIncompatibleVariableOverride]

    @override
    def _run(
        self,
        text: str,
        images: list[str] | None = None,
        video: str | None = None,
        post_id: str | None = None,
    ) -> str:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports asynchronous skill calls"
        )

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
        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ValueError("No AgentContext found")
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
