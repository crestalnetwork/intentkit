def agent_chat_id(
    guild_memory_public: bool, channel_id: int, guild_id: int | None = None
):
    """
    Generate chat_id similar to Telegram pattern.

    Args:
        guild_memory_public: If True, share memory across guild
        channel_id: Discord channel ID
        guild_id: Discord guild/server ID

    Returns:
        Chat ID string for memory management
    """
    if guild_memory_public and guild_id:
        return f"discord-guild-{guild_id}"
    return f"discord-channel-{channel_id}"
