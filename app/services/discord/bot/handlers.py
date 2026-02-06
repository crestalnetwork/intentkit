"""Discord message handlers.

Note: These handlers require the following intents to be enabled in Discord Developer Portal:
- Message Content Intent (Privileged) - Required to read message.content
- Server Members Intent (Privileged) - Optional, for member information

Without Message Content Intent enabled, the bot will receive messages but message.content will be empty.
"""

import logging

import discord
from epyxid import XID

from intentkit.core.engine import execute_agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import (
    AuthorType,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
    ChatMessageCreate,
)

from app.services.discord.bot.types.bot import BotPoolItem

logger = logging.getLogger(__name__)


async def on_ready_handler(bot_item: BotPoolItem):
    """Handle bot ready event."""
    logger.info(f"Discord bot {bot_item.bot.user} is ready")

    # Update agent data with bot info
    try:
        if not bot_item.bot.user:
            return
        agent_data = await AgentData.get(bot_item.agent_id)
        agent_data.discord_id = str(bot_item.bot.user.id)
        agent_data.discord_username = bot_item.bot.user.name
        agent_data.discord_name = bot_item.bot.user.display_name
        await agent_data.save()
    except Exception as e:
        logger.error(f"Failed to update agent data: {e}")


async def on_message_handler(message: discord.Message, bot_item: BotPoolItem):
    """Handle incoming Discord messages."""
    from app.services.discord.bot.utils import agent_chat_id

    # Don't respond to self
    if not bot_item.bot.user or message.author == bot_item.bot.user:
        return

    # Check if should respond
    if not await should_respond(message, bot_item):
        return

    # Show typing indicator
    async with message.channel.typing():
        try:
            # Determine chat_id
            if isinstance(message.channel, discord.DMChannel):
                chat_id = f"discord-dm-{message.author.id}"
            else:
                chat_id = agent_chat_id(
                    bot_item.guild_memory_public,
                    message.channel.id,
                    message.guild.id if message.guild else None,
                )

            # Check if owner
            is_owner = bot_item.owner_discord_id and str(message.author.id) == str(
                bot_item.owner_discord_id
            )

            # Create standardized message
            attachments: list[ChatMessageAttachment] | None = None
            if message.attachments:
                attachments = []
                for att in message.attachments:
                    att_type = ChatMessageAttachmentType.FILE
                    if att.content_type and att.content_type.startswith("image/"):
                        att_type = ChatMessageAttachmentType.IMAGE

                    attachments.append(
                        {
                            "type": att_type,
                            "url": att.url,
                            "json": {
                                "filename": att.filename,
                                "content_type": att.content_type,
                            },
                        }
                    )

            input_message = ChatMessageCreate(
                id=str(XID()),
                agent_id=bot_item.agent_id,
                chat_id=chat_id,
                user_id=bot_item.agent_owner if is_owner else str(message.author.id),
                author_id=str(message.author.id),
                author_type=AuthorType.DISCORD,
                thread_type=AuthorType.DISCORD,
                message=message.content,
                attachments=attachments,
            )

            # Execute agent
            response = await execute_agent(input_message)

            # Send response
            response_text = response[-1].message if response else "Server Error"

            # Reply to the original message (like Telegram does)
            if len(response_text) <= 2000:
                _ = await message.reply(response_text)
            else:
                # For long messages, split and send first as reply, rest as regular messages
                chunks = [
                    response_text[i : i + 2000]
                    for i in range(0, len(response_text), 2000)
                ]
                _ = await message.reply(chunks[0])
                for chunk in chunks[1:]:
                    _ = await message.channel.send(chunk)

        except Exception as e:
            logger.error(f"Error processing Discord message: {e}")
            _ = await message.channel.send("Sorry, I encountered an error.")


async def should_respond(message: discord.Message, bot_item: BotPoolItem) -> bool:
    """
    Determine if bot should respond to this message.

    Similar to Telegram pattern:
    - DMs: respond to all messages
    - Servers: only respond to mentions or replies
    """
    # DM handling - respond to all messages
    if isinstance(message.channel, discord.DMChannel):
        return bot_item.respond_to_dm

    # Guild whitelist check
    if bot_item.guild_whitelist:
        if message.guild and message.guild.id not in bot_item.guild_whitelist:
            return False

    # Channel whitelist check
    if bot_item.channel_whitelist:
        if message.channel.id not in bot_item.channel_whitelist:
            return False

    # Check if bot was mentioned
    if bot_item.bot.user in message.mentions:
        return bot_item.respond_to_mentions

    # Check if replying to bot's message
    if message.reference and message.reference.resolved:
        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message):
            if resolved.author == bot_item.bot.user:
                return bot_item.respond_to_replies

    return False


async def send_discord_response(channel: discord.abc.Messageable, text: str):
    """
    Send response, splitting if over Discord's 2000 char limit.

    Args:
        channel: Discord channel to send to
        text: Message text to send
    """
    if len(text) <= 2000:
        _ = await channel.send(text)
    else:
        # Split into chunks of 2000 characters
        chunks = [text[i : i + 2000] for i in range(0, len(text), 2000)]
        for chunk in chunks:
            _ = await channel.send(chunk)
