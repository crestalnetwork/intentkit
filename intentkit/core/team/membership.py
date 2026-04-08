"""Team management functions."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.models.team import (
    PLAN_CONFIGS,
    Team,
    TeamCreate,
    TeamInvite,
    TeamInviteTable,
    TeamMember,
    TeamMemberTable,
    TeamPlan,
    TeamRole,
    TeamTable,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_TEAM_ID_PATTERN = re.compile(r"^[a-z]([a-z0-9-]*[a-z0-9])?$")

_ROLE_LEVELS: dict[TeamRole, int] = {
    TeamRole.MEMBER: 0,
    TeamRole.ADMIN: 1,
    TeamRole.OWNER: 2,
}

_TEAM_AVATAR_SYSTEM_PROMPT = """\
You are an expert logo/avatar designer for teams and organizations. \
Based on the team name below, write a concise visual description for a team avatar.

Requirements for the avatar:
- Modern, clean, and visually striking design suitable as a team profile picture
- A single central icon or symbol that represents the team's identity
- Professional and memorable, works well at small sizes (like a chat avatar)
- Abstract or stylized — do NOT include any text, letters, or words in the image
- Use colors and shapes that feel collaborative and professional
- Square composition with the subject centered

Output ONLY the image generation prompt, nothing else."""

_CACHE_TEAM_PREFIX = "intentkit:team:"
_CACHE_ROLE_PREFIX = "intentkit:team_role:"
_CACHE_TTL = 3600


def validate_team_id_format(team_id: str) -> dict[str, bool | str | None]:
    """Validate team ID format only.

    Returns:
        {"valid": bool, "reason": str | None}
    """
    if len(team_id) < 3:
        return {"valid": False, "reason": "Team ID must be at least 3 characters"}
    if len(team_id) > 20:
        return {"valid": False, "reason": "Team ID must be at most 20 characters"}
    if not _TEAM_ID_PATTERN.match(team_id):
        return {
            "valid": False,
            "reason": "Team ID must start with a letter, contain only lowercase letters, digits, and hyphens, and not end with a hyphen",
        }
    return {"valid": True, "reason": None}


async def validate_team_id(team_id: str) -> dict[str, bool | str | None]:
    """Validate team ID format and uniqueness.

    Returns:
        {"valid": bool, "reason": str | None}
    """
    fmt = validate_team_id_format(team_id)
    if not fmt["valid"]:
        return fmt

    existing = await Team.get(team_id)
    if existing:
        return {"valid": False, "reason": "Team ID is already taken"}

    return {"valid": True, "reason": None}


async def generate_team_avatar(team_id: str, team_name: str) -> str | None:
    """Generate an avatar for a team and upload to S3.

    Returns:
        The image path (without CDN prefix), or None on failure.
    """
    from epyxid import XID

    from intentkit.clients.s3 import store_image_bytes
    from intentkit.core.avatar import (
        generate_image_prompt_from_profile,
        select_model_and_generate,
    )

    try:
        profile = f"Team Name: {team_name}"
        image_prompt = await generate_image_prompt_from_profile(
            profile, _TEAM_AVATAR_SYSTEM_PROMPT
        )
        logger.info(
            "Generated avatar prompt for team %s: %s", team_id, image_prompt[:200]
        )
    except Exception as e:
        logger.error("Failed to generate avatar prompt for team %s: %s", team_id, e)
        image_prompt = (
            f"A modern, minimalist, professional team avatar for a team called '{team_name}'. "
            f"Abstract geometric design, vibrant gradient colors, clean lines, centered composition, no text."
        )

    image_bytes = await select_model_and_generate(image_prompt)
    if not image_bytes:
        return None

    try:
        key = f"avatars/team/{team_id}/{XID()}.png"
        relative_path = await store_image_bytes(
            image_bytes, key, content_type="image/png"
        )
        if not relative_path:
            logger.error("store_image_bytes returned empty path for team %s", team_id)
            return None
        return relative_path
    except Exception as e:
        logger.error("Failed to upload team avatar to S3: %s", e)
        return None


async def create_team(team_id: str, name: str, creator_user_id: str) -> Team:
    """Create a new team with avatar generation.

    Raises:
        ValueError: If team ID format is invalid or already taken.
    """
    validation = await validate_team_id(team_id)
    if not validation["valid"]:
        raise ValueError(str(validation["reason"]))

    # Generate avatar (failure does not block creation)
    avatar: str | None = None
    try:
        avatar = await generate_team_avatar(team_id, name)
    except Exception as e:
        logger.warning("Avatar generation failed for team %s: %s", team_id, e)

    team_create = TeamCreate(id=team_id, name=name, avatar=avatar, default_channel=None)
    return await team_create.save(creator_user_id)


async def get_team(team_id: str) -> Team | None:
    """Get a team by ID, with Redis caching (TTL 3600s)."""
    redis = get_redis()
    cache_key = f"{_CACHE_TEAM_PREFIX}{team_id}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            return Team.model_validate_json(cached)
    except Exception as e:
        logger.warning("Redis cache read failed for team %s: %s", team_id, e)

    team = await Team.get(team_id)
    if team:
        try:
            await redis.set(cache_key, team.model_dump_json(), ex=_CACHE_TTL)
        except Exception as e:
            logger.warning("Redis cache write failed for team %s: %s", team_id, e)

    return team


async def update_team(
    team_id: str,
    *,
    name: str | None = None,
    avatar: str | None = None,
) -> Team:
    """Update team name and/or avatar.

    Raises:
        ValueError: If team not found or no updates provided.
    """
    if name is None and avatar is None:
        raise ValueError("No updates provided")

    from sqlalchemy import update

    async with get_session() as db:
        values: dict[str, str] = {}
        if name is not None:
            values["name"] = name
        if avatar is not None:
            values["avatar"] = avatar

        stmt = update(TeamTable).where(TeamTable.id == team_id).values(**values)
        cursor = await db.execute(stmt)
        if cursor.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
            raise ValueError(f"Team {team_id} not found")
        await db.commit()

    # Invalidate cache
    try:
        redis = get_redis()
        await redis.delete(f"{_CACHE_TEAM_PREFIX}{team_id}")
    except Exception as e:
        logger.warning("Failed to invalidate team cache for %s: %s", team_id, e)

    team = await Team.get(team_id)
    if not team:
        raise ValueError(f"Team {team_id} not found after update")
    return team


async def create_invite(
    team_id: str,
    invited_by: str,
    role: TeamRole = TeamRole.MEMBER,
    max_uses: int | None = None,
    expires_at: datetime | None = None,
) -> TeamInvite:
    """Create a team invite.

    Raises:
        ValueError: If team does not exist.
    """
    team = await Team.get(team_id)
    if not team:
        raise ValueError(f"Team {team_id} not found")

    async with get_session() as db:
        invite = TeamInviteTable(
            team_id=team_id,
            invited_by=invited_by,
            role=role,
            max_uses=max_uses,
            expires_at=expires_at,
        )
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
        return TeamInvite.model_validate(invite)


async def join_team(code: str, user_id: str) -> Team:
    """Join a team using an invite code.

    Raises:
        ValueError: If invite is invalid, expired, or used up,
                    or if user is already a member.
    """
    from sqlalchemy import func, select, update

    async with get_session() as db:
        # Find invite with row lock to prevent race conditions
        stmt = (
            select(TeamInviteTable)
            .where(TeamInviteTable.code == code)
            .with_for_update()
        )
        result = await db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            raise ValueError("Invalid invite code")

        # Check expiry
        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            raise ValueError("Invite has expired")

        # Check usage limit
        if invite.max_uses is not None and invite.use_count >= invite.max_uses:
            raise ValueError("Invite has reached maximum uses")

        # Check if already a member
        member_stmt = select(TeamMemberTable).where(
            TeamMemberTable.team_id == invite.team_id,
            TeamMemberTable.user_id == user_id,
        )
        existing = await db.execute(member_stmt)
        if existing.scalar_one_or_none():
            raise ValueError("User is already a member of this team")

        # Check seats limit
        team = await Team.get(invite.team_id)
        if team:
            cfg = PLAN_CONFIGS.get(team.plan, PLAN_CONFIGS[TeamPlan.NONE])
            count_stmt = (
                select(func.count())
                .select_from(TeamMemberTable)
                .where(TeamMemberTable.team_id == invite.team_id)
            )
            member_count = await db.scalar(count_stmt) or 0
            if member_count >= cfg.seats:
                raise ValueError(
                    f"Team has reached the maximum number of seats "
                    f"({cfg.seats}) for the {cfg.name} plan"
                )

        # Capture values before commit (expire_on_commit=True)
        invite_team_id = invite.team_id
        invite_role = invite.role
        invite_id = invite.id

        # Add member
        member = TeamMemberTable(
            team_id=invite_team_id,
            user_id=user_id,
            role=invite_role,
        )
        db.add(member)

        # Atomic increment use count
        update_stmt = (
            update(TeamInviteTable)
            .where(TeamInviteTable.id == invite_id)
            .values(use_count=TeamInviteTable.use_count + 1)
        )
        await db.execute(update_stmt)

        await db.commit()

    team = await Team.get(invite_team_id)
    if not team:
        raise ValueError("Team not found")
    return team


async def _get_member_role(db: "AsyncSession", team_id: str, user_id: str) -> TeamRole:
    """Get member's role or raise ValueError if not found."""
    from sqlalchemy import select

    stmt = select(TeamMemberTable.role).where(
        TeamMemberTable.team_id == team_id,
        TeamMemberTable.user_id == user_id,
    )
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()
    if role is None:
        raise ValueError("Member not found")
    return TeamRole(role.value if hasattr(role, "value") else str(role))


async def _ensure_not_last_owner(db: "AsyncSession", team_id: str) -> None:
    """Raise ValueError if there is only one owner left."""
    from sqlalchemy import func, select

    owner_count_stmt = (
        select(func.count())
        .select_from(TeamMemberTable)
        .where(
            TeamMemberTable.team_id == team_id,
            TeamMemberTable.role == TeamRole.OWNER,
        )
    )
    owner_count = await db.scalar(owner_count_stmt)
    if (owner_count or 0) <= 1:
        raise ValueError("Cannot remove or demote the last owner")


async def _invalidate_role_cache(team_id: str, user_id: str) -> None:
    """Delete cached role entry from Redis."""
    try:
        redis = get_redis()
        await redis.delete(f"{_CACHE_ROLE_PREFIX}{team_id}:{user_id}")
    except Exception as e:
        logger.warning(
            "Failed to invalidate role cache for %s:%s: %s", team_id, user_id, e
        )


async def change_member_role(team_id: str, user_id: str, new_role: TeamRole) -> None:
    """Change a team member's role.

    Raises:
        ValueError: If member not found or trying to demote last owner.
    """
    from sqlalchemy import update

    async with get_session() as db:
        current_role = await _get_member_role(db, team_id, user_id)

        if current_role == TeamRole.OWNER and new_role != TeamRole.OWNER:
            await _ensure_not_last_owner(db, team_id)

        update_stmt = (
            update(TeamMemberTable)
            .where(
                TeamMemberTable.team_id == team_id,
                TeamMemberTable.user_id == user_id,
            )
            .values(role=new_role)
        )
        await db.execute(update_stmt)
        await db.commit()

    await _invalidate_role_cache(team_id, user_id)


async def remove_member(team_id: str, user_id: str) -> None:
    """Remove a member from a team.

    Raises:
        ValueError: If member not found or trying to remove the last owner.
    """
    from sqlalchemy import delete

    async with get_session() as db:
        current_role = await _get_member_role(db, team_id, user_id)

        if current_role == TeamRole.OWNER:
            await _ensure_not_last_owner(db, team_id)

        del_stmt = delete(TeamMemberTable).where(
            TeamMemberTable.team_id == team_id,
            TeamMemberTable.user_id == user_id,
        )
        await db.execute(del_stmt)
        await db.commit()

    await _invalidate_role_cache(team_id, user_id)


async def get_members(team_id: str) -> list["TeamMember"]:
    """Get all members of a team, including user profile info."""
    from sqlalchemy import select

    from intentkit.models.user import UserTable

    async with get_session() as db:
        stmt = (
            select(
                TeamMemberTable,
                UserTable.name,
                UserTable.email,
                UserTable.evm_wallet_address,
            )
            .outerjoin(UserTable, UserTable.id == TeamMemberTable.user_id)
            .where(TeamMemberTable.team_id == team_id)
        )
        result = await db.execute(stmt)
        members = []
        for row in result:
            member_row, name, email, evm_wallet = row.tuple()
            m = TeamMember.model_validate(member_row)
            m.name = name
            m.email = email
            m.evm_wallet_address = evm_wallet
            members.append(m)
        return members


async def check_permission(team_id: str, user_id: str, required_role: TeamRole) -> bool:
    """Check if a user has the required role in a team.

    Uses Redis cache for role lookups (TTL 3600s).
    """
    redis = get_redis()
    cache_key = f"{_CACHE_ROLE_PREFIX}{team_id}:{user_id}"

    # Try cache first
    user_role_str: str | None = None
    try:
        user_role_str = await redis.get(cache_key)
    except Exception as e:
        logger.warning(
            "Redis cache read failed for role %s:%s: %s", team_id, user_id, e
        )

    if user_role_str is None:
        # Cache miss — query DB
        from sqlalchemy import select

        async with get_session() as db:
            stmt = select(TeamMemberTable.role).where(
                TeamMemberTable.team_id == team_id,
                TeamMemberTable.user_id == user_id,
            )
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()

        if row is None:
            return False

        user_role_str = str(row.value if hasattr(row, "value") else row)
        try:
            await redis.set(cache_key, user_role_str, ex=_CACHE_TTL)
        except Exception as e:
            logger.warning(
                "Redis cache write failed for role %s:%s: %s", team_id, user_id, e
            )

    try:
        user_role = TeamRole(user_role_str)
    except ValueError:
        return False

    return _ROLE_LEVELS[user_role] >= _ROLE_LEVELS[required_role]
