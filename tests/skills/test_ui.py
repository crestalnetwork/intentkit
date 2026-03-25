"""Tests for UI skills."""

import pytest

from intentkit.models.chat import ChatMessageAttachmentType
from intentkit.skills.ui.ask_user import UIAskUser
from intentkit.skills.ui.show_card import UIShowCard


@pytest.mark.asyncio
async def test_show_card_basic():
    """Test UIShowCard returns correct attachment structure."""
    skill = UIShowCard()

    result = await skill._arun(
        title="Test Card",
    )

    content, attachments = result
    assert content == "Card displayed successfully."
    assert len(attachments) == 1

    att = attachments[0]
    assert att["type"] == ChatMessageAttachmentType.CARD
    assert att["url"] is None
    assert att["lead_text"] is None
    assert att["json"]["title"] == "Test Card"
    assert att["json"]["description"] is None
    assert att["json"]["label"] is None
    assert att["json"]["image_url"] is None


@pytest.mark.asyncio
async def test_show_card_with_lead_text_and_image():
    """Test UIShowCard with lead_text and image_url."""
    skill = UIShowCard()

    result = await skill._arun(
        title="Test Card",
        url="https://example.com",
        description="Description",
        label="Go",
        image_url="https://example.com/img.png",
        lead_text="Check this out:",
    )

    content, attachments = result
    assert content == "Card displayed successfully."
    att = attachments[0]
    assert att["lead_text"] == "Check this out:"
    assert att["url"] == "https://example.com"
    assert att["json"]["image_url"] == "https://example.com/img.png"
    assert att["json"]["description"] == "Description"
    assert att["json"]["label"] == "Go"


@pytest.mark.asyncio
async def test_ask_user_two_options():
    """Test UIAskUser with two options."""
    skill = UIAskUser()

    result = await skill._arun(
        lead_text="Which do you prefer?",
        option_a_title="Option A",
        option_a_content="First option",
        option_b_title="Option B",
        option_b_content="Second option",
    )

    content, attachments = result
    assert content == "Choice displayed successfully."
    assert len(attachments) == 1

    att = attachments[0]
    assert att["type"] == ChatMessageAttachmentType.CHOICE
    assert att["lead_text"] == "Which do you prefer?"
    assert att["url"] is None

    options = att["json"]
    assert "a" in options
    assert "b" in options
    assert "c" not in options
    assert options["a"]["title"] == "Option A"
    assert options["b"]["content"] == "Second option"


@pytest.mark.asyncio
async def test_ask_user_three_options():
    """Test UIAskUser with three options."""
    skill = UIAskUser()

    result = await skill._arun(
        lead_text="Pick one:",
        option_a_title="A",
        option_a_content="First",
        option_b_title="B",
        option_b_content="Second",
        option_c_title="C",
        option_c_content="Third",
    )

    _content, attachments = result
    att = attachments[0]
    options = att["json"]
    assert "c" in options
    assert options["c"]["title"] == "C"
    assert options["c"]["content"] == "Third"


def test_skill_metadata():
    """Test skill names and categories."""
    show_card = UIShowCard()
    assert show_card.name == "ui_show_card"
    assert show_card.category == "ui"
    assert show_card.response_format == "content_and_artifact"

    ask_user = UIAskUser()
    assert ask_user.name == "ui_ask_user"
    assert ask_user.category == "ui"
    assert ask_user.response_format == "content_and_artifact"
