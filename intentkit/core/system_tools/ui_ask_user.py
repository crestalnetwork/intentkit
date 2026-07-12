"""System tool for presenting the user with clickable options."""

from typing import Literal, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.system_tools.base import SystemTool
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType


class AskUserInput(BaseModel):
    """Input for UI ask user tool."""

    lead_text: str = Field(
        description="Question/prompt text displayed before the options"
    )
    option_a_title: str = Field(description="Title for option A")
    option_a_content: str = Field(description="Description for option A")
    option_b_title: str = Field(description="Title for option B")
    option_b_content: str = Field(description="Description for option B")
    option_c_title: str | None = Field(
        default=None, description="Optional title for option C"
    )
    option_c_content: str | None = Field(
        default=None, description="Optional description for option C"
    )


class UIAskUserTool(SystemTool):
    """Tool for presenting the user with a set of clickable options/choices."""

    name: str = "ui_ask_user"
    description: str = (
        "Present the user with 2-3 clickable options to choose from. "
        "Each option has a title and description. The user can click an option to respond."
    )
    args_schema: ArgsSchema | None = AskUserInput
    # Return a (content, artifact) tuple so the choice lands in attachments
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    interactive_only: bool = True
    # The choice payload in the result must survive context editing
    context_editing_exempt: bool = True
    # The turn ends here: the agent must wait for the user's pick
    return_direct: bool = True

    @override
    async def _arun(
        self,
        lead_text: str,
        option_a_title: str,
        option_a_content: str,
        option_b_title: str,
        option_b_content: str,
        option_c_title: str | None = None,
        option_c_content: str | None = None,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        options: dict[str, object] = {
            "a": {"title": option_a_title, "content": option_a_content},
            "b": {"title": option_b_title, "content": option_b_content},
        }
        if option_c_title and option_c_content:
            options["c"] = {"title": option_c_title, "content": option_c_content}

        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.CHOICE,
            "lead_text": lead_text,
            "url": None,
            "json": options,
        }
        return "Choice displayed successfully.", [attachment]
