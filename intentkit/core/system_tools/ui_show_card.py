"""System tool for displaying a rich card to the user."""

from typing import Literal, cast, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.system_tools.base import SystemTool
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType


class ShowCardInput(BaseModel):
    """Input for UI show card tool."""

    title: str = Field(description="Card title")
    url: str | None = Field(
        default=None, description="Link target when the card is clicked"
    )
    description: str | None = Field(default=None, description="Card body text")
    label: str | None = Field(
        default=None, description="Action label displayed on the card"
    )
    image_url: str | None = Field(default=None, description="Optional card image URL")
    lead_text: str | None = Field(
        default=None, description="Text displayed before the card"
    )


class UIShowCardTool(SystemTool):
    """Tool for displaying a rich card with title and optional description, image, label, and link."""

    name: str = "ui_show_card"
    description: str = (
        "Display a rich card to the user. Only title is required. "
        "Optionally include description, image, action label, and a clickable URL."
    )
    args_schema: ArgsSchema | None = ShowCardInput
    # Return a (content, artifact) tuple so the card lands in attachments
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    interactive_only: bool = True

    @override
    async def _arun(
        self,
        title: str,
        url: str | None = None,
        description: str | None = None,
        label: str | None = None,
        image_url: str | None = None,
        lead_text: str | None = None,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.CARD,
            "lead_text": lead_text,
            "url": url,
            "json": cast(
                dict[str, object],
                {
                    "title": title,
                    "description": description,
                    "label": label,
                    "image_url": image_url,
                },
            ),
        }
        return "Card displayed successfully.", [attachment]
