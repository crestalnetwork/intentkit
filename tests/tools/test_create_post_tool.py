import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.system_tools.create_post import (
    CreatePostInput,
    CreatePostTool,
    _truncate_slug,
)
from intentkit.models.agent_activity import AgentActivityTable
from intentkit.models.agent_post import SLUG_MAX_LENGTH, AgentPostTable


@pytest.fixture
def mock_db_session():
    """Fixture for mocked database session."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Default refresh side effect
    def side_effect_refresh(instance):
        if not instance.id:
            instance.id = f"mock_id_{uuid.uuid4().hex}"
        if not instance.created_at:
            instance.created_at = datetime.now()

    mock_session.refresh.side_effect = side_effect_refresh

    mock_get_session_cm = AsyncMock()
    mock_get_session_cm.__aenter__.return_value = mock_session
    mock_get_session_cm.__aexit__.return_value = None

    with (
        patch(
            "intentkit.core.agent_post.get_session", return_value=mock_get_session_cm
        ),
        patch(
            "intentkit.core.agent_activity.get_session",
            return_value=mock_get_session_cm,
        ),
    ):
        yield mock_session


async def _run_create_post(**kwargs):
    """Run CreatePostTool._arun with runtime/agent lookups patched out."""
    tool = CreatePostTool()
    mock_context = MagicMock()
    mock_context.agent_id = "test_agent_123"
    mock_agent = MagicMock()
    mock_agent.name = "Test Agent"
    mock_agent.picture = "https://example.com/avatar.png"
    with (
        patch("intentkit.core.agent.get_agent", new=AsyncMock(return_value=mock_agent)),
        patch(
            "intentkit.core.system_tools.create_post.CreatePostTool.get_context",
            return_value=mock_context,
        ),
    ):
        return await tool._arun(**kwargs)


def _stored(mock_db_session, cls):
    """Return the first object of the given table class added to the session."""
    added = [call[0][0] for call in mock_db_session.add.call_args_list]
    return next((obj for obj in added if isinstance(obj, cls)), None)


@pytest.mark.asyncio
async def test_create_post_success(mock_db_session):
    """Test successful post creation."""
    title = "Test Post Title"
    slug = "test-post-title"
    excerpt = "Short excerpt."
    tags = ["tag1", "tag2"]

    content, attachments = await _run_create_post(
        title=title,
        markdown="This is the content.",
        slug=slug,
        excerpt=excerpt,
        tags=tags,
    )

    assert "Post created successfully" in content
    assert isinstance(attachments, list)
    assert len(attachments) == 1

    # Verify post creation
    assert mock_db_session.add.call_count == 2

    post_obj = _stored(mock_db_session, AgentPostTable)
    activity_obj = _stored(mock_db_session, AgentActivityTable)

    assert post_obj is not None
    assert post_obj.slug == slug
    assert post_obj.excerpt == excerpt
    assert post_obj.tags == tags

    # Verify activity creation
    assert activity_obj is not None
    assert post_obj.id == activity_obj.post_id


def test_truncate_slug():
    """Overlong slugs are cut to the limit, preferring a hyphen boundary."""
    # Fits: passes through untouched
    assert _truncate_slug("short-slug") == "short-slug"
    # No hyphen before the limit: hard cut
    assert _truncate_slug("a" * 70) == "a" * SLUG_MAX_LENGTH
    # Hyphen boundary: the half word after the last hyphen is dropped
    assert _truncate_slug("a" * 30 + "-" + "b" * 30) == "a" * 30
    # Early hyphen must not eat the whole budget: hard cut instead
    assert _truncate_slug("a-" + "b" * 100) == "a-" + "b" * (SLUG_MAX_LENGTH - 2)
    # Pathological all-hyphen input still yields a non-empty slug
    assert _truncate_slug("-" * 70) == "-" * SLUG_MAX_LENGTH


@pytest.mark.asyncio
async def test_create_post_truncates_overlong_slug(mock_db_session):
    """An overlong slug from the LLM is stored truncated, not rejected."""
    content, _ = await _run_create_post(
        title="Title",
        markdown="Content",
        slug="a" * 30 + "-" + "b" * 30,
        excerpt="Excerpt",
        tags=["tag1"],
    )

    assert "Post created successfully" in content
    post_obj = _stored(mock_db_session, AgentPostTable)
    assert post_obj is not None
    assert post_obj.slug == "a" * 30


def test_create_post_input_validation():
    """Test input validation for CreatePostInput."""

    # Test valid input
    CreatePostInput(
        title="Valid Title",
        markdown="Content",
        slug="valid-slug-123",
        excerpt="Valid excerpt",
        tags=["tag1"],
    )

    # Overlong slug passes the schema: LLMs occasionally overshoot and a
    # hard rejection wastes a whole turn. It is truncated later in _arun.
    CreatePostInput(
        title="Valid Title",
        markdown="Content",
        slug="a" * 61,
        excerpt="Valid excerpt",
        tags=["tag1"],
    )

    # Test invalid slug (bad chars)
    with pytest.raises(Exception):
        CreatePostInput(
            title="Valid Title",
            markdown="Content",
            slug="bad slug",
            excerpt="Valid excerpt",
            tags=["tag1"],
        )

    # Test invalid excerpt (too long)
    with pytest.raises(Exception):
        CreatePostInput(
            title="Valid Title",
            markdown="Content",
            slug="valid-slug-123",
            excerpt="a" * 201,
            tags=["tag1"],
        )

    # Test invalid tags (too many)
    with pytest.raises(Exception):
        CreatePostInput(
            title="Valid Title",
            markdown="Content",
            slug="valid-slug-123",
            excerpt="Valid excerpt",
            tags=["1", "2", "3", "4"],
        )
