import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.core.system_skills.create_post import CreatePostInput, CreatePostSkill
from intentkit.models.agent_activity import AgentActivityTable
from intentkit.models.agent_post import AgentPostTable


@pytest.fixture
def mock_runtime():
    """Fixture for mocked runtime context."""
    agent_id = "test_agent_123"
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = agent_id

    with patch(
        "intentkit.core.system_skills.create_post.get_runtime"
    ) as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime


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


@pytest.mark.asyncio
async def test_create_post_success(mock_runtime, mock_db_session):
    """Test successful post creation."""
    skill = CreatePostSkill()

    title = "Test Post Title"
    markdown = "This is the content."
    slug = "test-post-title"
    excerpt = "Short excerpt."
    tags = ["tag1", "tag2"]

    mock_agent = MagicMock()
    mock_agent.name = "Test Agent"
    with patch(
        "intentkit.core.agent.get_agent",
        new=AsyncMock(return_value=mock_agent),
    ):
        result = await skill._arun(
            title=title, markdown=markdown, slug=slug, excerpt=excerpt, tags=tags
        )

    assert "Post created successfully" in result

    # Verify post creation
    assert mock_db_session.add.call_count == 2

    added_objects = [call[0][0] for call in mock_db_session.add.call_args_list]
    post_obj = next(
        (obj for obj in added_objects if isinstance(obj, AgentPostTable)), None
    )
    activity_obj = next(
        (obj for obj in added_objects if isinstance(obj, AgentActivityTable)), None
    )

    assert post_obj is not None
    assert post_obj.slug == slug
    assert post_obj.excerpt == excerpt
    assert post_obj.tags == tags

    # Verify activity creation
    assert activity_obj is not None
    assert post_obj.id == activity_obj.post_id


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

    # Test invalid slug (too long)
    with pytest.raises(Exception):  # Pydantic ValidationError
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
