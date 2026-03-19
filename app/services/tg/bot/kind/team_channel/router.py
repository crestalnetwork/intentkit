"""Telegram router for team channel bots.

Routes messages through the lead engine (stream_lead) instead of
the regular agent executor. Requires Telegram sender to be bound
to an IntentKit user who is a member of the team.
"""

import logging

import telegramify_markdown
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReactionTypeEmoji
from epyxid import XID

from intentkit.core.lead.engine import stream_lead
from intentkit.core.lead.service import verify_team_membership
from intentkit.models.chat import AuthorType, ChatMessageCreate
from intentkit.models.user import User
from intentkit.utils.error import IntentKitAPIError

from app.services.tg.bot.filter.content_type import TextOnlyFilter
from app.services.tg.bot.filter.no_bot import NoBotFilter

logger = logging.getLogger(__name__)

team_channel_router = Router()


async def _resolve_user(telegram_id: int) -> User | None:
    """Resolve Telegram user ID to IntentKit user."""
    return await User.get_by_telegram_id(str(telegram_id))


@team_channel_router.message(CommandStart(), NoBotFilter(), TextOnlyFilter())
async def command_start(message: Message) -> None:
    try:
        _ = await message.answer(
            text="Welcome! This is a team channel bot. "
            "Please bind your Telegram account to your IntentKit user to interact."
        )
    except Exception as e:
        logger.warning("Error in team channel /start: %s", e)


@team_channel_router.message(TextOnlyFilter(), NoBotFilter())
async def process_team_message(message: Message) -> None:
    from app.services.tg.bot.cache import team_channel_bot_by_token

    if not message.bot or not message.bot.token:
        return

    bot_item = team_channel_bot_by_token(message.bot.token)
    if not bot_item:
        logger.warning("Team channel bot not found in cache for token")
        return

    if not message.from_user:
        return

    # Resolve Telegram sender → IntentKit user
    user = await _resolve_user(message.from_user.id)
    if not user:
        logger.debug(
            "Ignoring message from unbound Telegram user %d in team %s",
            message.from_user.id,
            bot_item.team_id,
        )
        return

    # Verify team membership before processing
    try:
        await verify_team_membership(bot_item.team_id, user.id)
    except IntentKitAPIError:
        logger.debug(
            "User %s is not a member of team %s, ignoring message",
            user.id,
            bot_item.team_id,
        )
        return

    _ = await message.react([ReactionTypeEmoji(emoji="🤔")])

    try:
        if not message.text:
            return

        chat_msg = ChatMessageCreate(
            id=str(XID()),
            agent_id=bot_item.team_id,
            chat_id=f"tg_team:{bot_item.team_id}:{message.chat.id}",
            user_id=user.id,
            author_id=user.id,
            author_type=AuthorType.TELEGRAM,
            thread_type=AuthorType.TELEGRAM,
            message=message.text,
        )

        # Collect all messages from stream_lead
        last_message = None
        async for chat_message in stream_lead(bot_item.team_id, user.id, chat_msg):
            last_message = chat_message

        response_text = last_message.message if last_message else "No response"
        _ = await message.answer(
            text=telegramify_markdown.markdownify(response_text),
            parse_mode="MarkdownV2",
        )

    except Exception as e:
        logger.warning("Error processing team channel message: %s", e)
        _ = await message.answer(text="Server Error")
    finally:
        try:
            _ = await message.react([])
        except Exception as e:
            logger.warning("Failed to remove reaction: %s", e)
