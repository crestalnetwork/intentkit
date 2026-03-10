from typing import cast, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.skills.ui.base import UIBaseTool


class ShowCardInput(BaseModel):
    """Input for UI show card skill."""

    title: str = Field(description="Card title")
    url: str | None = Field(default=None, description="Link target when the card is clicked")
    description: str | None = Field(default=None, description="Card body text")
    label: str | None = Field(default=None, description="Action label displayed on the card")
    image_url: str | None = Field(default=None, description="Optional card image URL")
    lead_text: str | None = Field(
        default=None, description="Text displayed before the card"
    )


class UIShowCard(UIBaseTool):
    """Skill for displaying a rich card with title and optional description, image, label, and link."""

    name: str = "ui_show_card"
    description: str = (
        "Display a rich card to the user. Only title is required. "
        "Optionally include description, image, action label, and a clickable URL."
    )
    args_schema: ArgsSchema | None = ShowCardInput

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
