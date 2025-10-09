"""Discord bot pool item."""
import discord

from intentkit.models.agent import Agent


class BotPoolItem:
    """Represents a Discord bot instance in the pool."""

    def __init__(self, agent: Agent):
        self._agent_id = agent.id
        self._agent_owner = agent.owner
        self._token = agent.discord_config.get("token") if agent.discord_config else None

        if not self._token:
            raise ValueError("Discord token cannot be empty")

        # Discord bot setup with required intents
        intents = discord.Intents.default()
        intents.message_content = True  # Privileged: Required for reading message content
        intents.guilds = True  # Required for guild events
        intents.guild_messages = True  # Required for receiving guild messages
        intents.dm_messages = True  # Required for receiving DMs
        # Note: message_content intent must be enabled in Discord Developer Portal

        # Use Client instead of Bot since we're not using commands
        self._bot = discord.Client(intents=intents)

        self.update_conf(agent.discord_config or {})

    def update_conf(self, config: dict):
        """Update bot configuration from agent config."""
        self._guild_whitelist = config.get("guild_whitelist")
        self._channel_whitelist = config.get("channel_whitelist")
        self._respond_to_mentions = config.get("respond_to_mentions", True)
        self._respond_to_replies = config.get("respond_to_replies", True)
        self._respond_to_dm = config.get("respond_to_dm", True)
        self._guild_memory_public = config.get("guild_memory_public", False)
        self._greeting_server = config.get(
            "greeting_server", "Hello! Mention me or reply to my messages to chat."
        )
        self._greeting_dm = config.get("greeting_dm", "Hello! Send me a message to chat.")
        self._owner_discord_id = config.get("owner_discord_id")

    @property
    def agent_id(self):
        return self._agent_id

    @property
    def agent_owner(self):
        return self._agent_owner

    @property
    def token(self):
        return self._token

    @property
    def bot(self):
        return self._bot

    @property
    def guild_whitelist(self):
        return self._guild_whitelist

    @property
    def channel_whitelist(self):
        return self._channel_whitelist

    @property
    def respond_to_mentions(self):
        return self._respond_to_mentions

    @property
    def respond_to_replies(self):
        return self._respond_to_replies

    @property
    def respond_to_dm(self):
        return self._respond_to_dm

    @property
    def guild_memory_public(self):
        return self._guild_memory_public

    @property
    def greeting_server(self):
        return self._greeting_server

    @property
    def greeting_dm(self):
        return self._greeting_dm

    @property
    def owner_discord_id(self):
        return self._owner_discord_id
