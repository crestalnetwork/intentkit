"""Tests for Team, Chat, and Draft model validation and serialization.

Pure Pydantic validation tests — no DB or async required.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from intentkit.models.chat import (
    AuthorType,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
    ChatMessageCreate,
)
from intentkit.models.draft import AgentDraft
from intentkit.models.team import TeamCreate, TeamInvite, TeamMember, TeamRole

# ---------------------------------------------------------------------------
# Team Models
# ---------------------------------------------------------------------------


class TestTeamRole:
    def test_team_role_values(self):
        assert TeamRole.OWNER == "owner"
        assert TeamRole.ADMIN == "admin"
        assert TeamRole.MEMBER == "member"


class TestTeamCreate:
    def test_team_create_valid(self):
        team = TeamCreate(id="my-team", name="My Team")
        assert team.id == "my-team"
        assert team.name == "My Team"
        assert team.avatar is None
        assert team.default_channel is None

    def test_team_create_invalid_id_pattern(self):
        """Uppercase letters are not allowed in team IDs."""
        with pytest.raises(ValidationError):
            TeamCreate(id="My-Team", name="My Team")

    def test_team_create_id_too_short(self):
        """ID must be at least 2 characters."""
        with pytest.raises(ValidationError):
            TeamCreate(id="a", name="My Team")

    def test_team_create_id_too_long(self):
        """ID must be at most 60 characters."""
        with pytest.raises(ValidationError):
            TeamCreate(id="a" * 61, name="My Team")

    def test_team_create_id_cannot_start_with_number(self):
        with pytest.raises(ValidationError):
            TeamCreate(id="1abc", name="My Team")

    def test_team_create_id_cannot_end_with_hyphen(self):
        with pytest.raises(ValidationError):
            TeamCreate(id="abc-", name="My Team")


class TestTeamMember:
    def test_team_member_joined_at_serializer(self):
        now = datetime(2025, 1, 15, 12, 30, 45, 123456, tzinfo=UTC)
        member = TeamMember(
            user_id="user-1",
            team_id="team-1",
            role=TeamRole.MEMBER,
            joined_at=now,
        )
        data = member.model_dump(mode="json")
        # Should be ISO format with milliseconds
        assert data["joined_at"] == "2025-01-15T12:30:45.123+00:00"


class TestTeamInvite:
    def test_team_invite_serializer(self):
        created = datetime(2025, 3, 1, 10, 0, 0, 0, tzinfo=UTC)
        expires = datetime(2025, 3, 8, 10, 0, 0, 0, tzinfo=UTC)
        invite = TeamInvite(
            id="inv-1",
            team_id="team-1",
            code="abc123",
            invited_by="user-1",
            role=TeamRole.MEMBER,
            max_uses=5,
            use_count=0,
            expires_at=expires,
            created_at=created,
        )
        data = invite.model_dump(mode="json")
        assert data["created_at"] == "2025-03-01T10:00:00.000+00:00"
        assert data["expires_at"] == "2025-03-08T10:00:00.000+00:00"

    def test_team_invite_serializer_none_expires(self):
        created = datetime(2025, 3, 1, 10, 0, 0, 0, tzinfo=UTC)
        invite = TeamInvite(
            id="inv-1",
            team_id="team-1",
            code="abc123",
            invited_by="user-1",
            role=TeamRole.ADMIN,
            max_uses=None,
            use_count=0,
            expires_at=None,
            created_at=created,
        )
        data = invite.model_dump(mode="json")
        assert data["expires_at"] is None
        assert data["created_at"] == "2025-03-01T10:00:00.000+00:00"


# ---------------------------------------------------------------------------
# Chat Models
# ---------------------------------------------------------------------------


class TestAuthorType:
    def test_author_type_values(self):
        assert AuthorType.AGENT == "agent"
        assert AuthorType.SYSTEM == "system"
        assert AuthorType.SKILL == "skill"
        assert AuthorType.THINKING == "thinking"
        assert AuthorType.TRIGGER == "trigger"
        assert AuthorType.TELEGRAM == "telegram"
        assert AuthorType.TWITTER == "twitter"
        assert AuthorType.DISCORD == "discord"
        assert AuthorType.WEB == "web"
        assert AuthorType.API == "api"


class TestChatMessageAttachmentType:
    def test_attachment_type_values(self):
        assert ChatMessageAttachmentType.LINK == "link"
        assert ChatMessageAttachmentType.IMAGE == "image"
        assert ChatMessageAttachmentType.VIDEO == "video"
        assert ChatMessageAttachmentType.FILE == "file"
        assert ChatMessageAttachmentType.XMTP == "xmtp"
        assert ChatMessageAttachmentType.CARD == "card"
        assert ChatMessageAttachmentType.CHOICE == "choice"


class TestChatMessageCreate:
    def test_chat_message_create_minimal(self):
        """Only truly required fields: agent_id, chat_id, user_id, author_id, author_type, message."""
        msg = ChatMessageCreate(
            agent_id="agent-1",
            chat_id="chat-1",
            user_id="user-1",
            author_id="agent-1",
            author_type=AuthorType.AGENT,
            message="Hello world",
        )
        assert msg.agent_id == "agent-1"
        assert msg.chat_id == "chat-1"
        assert msg.message == "Hello world"
        # id should be auto-generated
        assert msg.id is not None and len(msg.id) > 0
        # defaults
        assert msg.attachments is None
        assert msg.input_tokens == 0
        assert msg.output_tokens == 0
        assert msg.time_cost == 0.0

    def test_chat_message_create_with_attachments(self):
        attachments: list[ChatMessageAttachment] = [
            ChatMessageAttachment(
                type=ChatMessageAttachmentType.LINK,
                lead_text="Check this out",
                url="https://example.com",
                json=None,
            ),
            ChatMessageAttachment(
                type=ChatMessageAttachmentType.IMAGE,
                lead_text=None,
                url="https://example.com/img.png",
                json=None,
            ),
        ]
        msg = ChatMessageCreate(
            agent_id="agent-1",
            chat_id="chat-1",
            user_id="user-1",
            author_id="agent-1",
            author_type=AuthorType.AGENT,
            message="See attachments",
            attachments=attachments,
        )
        assert msg.attachments is not None
        assert len(msg.attachments) == 2
        assert msg.attachments[0]["type"] == "link"

    def test_chat_message_create_excluded_fields(self):
        """team_id and call_depth are excluded from serialization."""
        msg = ChatMessageCreate(
            agent_id="agent-1",
            chat_id="chat-1",
            user_id="user-1",
            author_id="agent-1",
            author_type=AuthorType.AGENT,
            message="test",
            team_id="team-1",
            call_depth=2,
        )
        data = msg.model_dump()
        assert "team_id" not in data
        assert "call_depth" not in data


# ---------------------------------------------------------------------------
# Draft Models
# ---------------------------------------------------------------------------


class TestAgentDraft:
    def test_agent_draft_creation(self):
        """AgentDraft extends AgentUserInput with draft-specific fields.

        The 'model' field is inherited from AgentCore and is required,
        but its validator accepts None and fills in a default LLM model.
        """
        now = datetime.now(UTC)
        draft = AgentDraft(
            agent_id="my-agent",
            name="Test Agent",
            model="",
            created_at=now,
            updated_at=now,
        )
        assert draft.agent_id == "my-agent"
        assert draft.name == "Test Agent"
        # id should be auto-generated
        assert draft.id is not None and len(draft.id) > 0
        # optional fields default to None
        assert draft.owner is None
        assert draft.team_id is None
        assert draft.version is None
        assert draft.project_id is None
        assert draft.last_draft_id is None
        assert draft.deployed_at is None

    def test_agent_draft_with_all_draft_fields(self):
        now = datetime.now(UTC)
        draft = AgentDraft(
            id="draft-123",
            agent_id="my-agent",
            name="Test Agent",
            model="",
            owner="user-1",
            team_id="team-1",
            version="abc123",
            project_id="proj-1",
            last_draft_id="draft-100",
            deployed_at=now,
            created_at=now,
            updated_at=now,
        )
        assert draft.id == "draft-123"
        assert draft.owner == "user-1"
        assert draft.team_id == "team-1"
        assert draft.version == "abc123"
        assert draft.project_id == "proj-1"
        assert draft.last_draft_id == "draft-100"
        assert draft.deployed_at == now
