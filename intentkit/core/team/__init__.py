"""Team management package.

Re-exports all public symbols from membership module for backward compatibility.
"""

from intentkit.core.team.membership import (
    change_member_role,
    check_permission,
    create_invite,
    create_team,
    generate_team_avatar,
    get_team,
    join_team,
    update_team,
    validate_team_id,
    validate_team_id_format,
)

__all__ = [
    "change_member_role",
    "check_permission",
    "create_invite",
    "create_team",
    "generate_team_avatar",
    "get_team",
    "join_team",
    "update_team",
    "validate_team_id",
    "validate_team_id_format",
]
