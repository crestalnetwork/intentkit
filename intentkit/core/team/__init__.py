"""Team management package.

Re-exports all public symbols from membership, subscription, and feed modules.
"""

from intentkit.core.team.feed import (
    fan_out_activity,
    fan_out_post,
    query_activity_feed,
    query_post_feed,
)
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
from intentkit.core.team.subscription import (
    auto_subscribe_team,
    get_subscriptions,
    subscribe_agent,
    unsubscribe_agent,
)

__all__ = [
    "auto_subscribe_team",
    "change_member_role",
    "check_permission",
    "create_invite",
    "create_team",
    "fan_out_activity",
    "fan_out_post",
    "generate_team_avatar",
    "get_subscriptions",
    "get_team",
    "join_team",
    "query_activity_feed",
    "query_post_feed",
    "subscribe_agent",
    "unsubscribe_agent",
    "update_team",
    "validate_team_id",
    "validate_team_id_format",
]
