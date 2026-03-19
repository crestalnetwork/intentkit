from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from intentkit.models.team_channel import TeamChannel

from app.services.tg.utils.cleanup import clean_token_str


class TeamChannelBotItem:
    """Bot pool item for team channel bots."""

    def __init__(self, channel: TeamChannel):
        if not channel.config:
            raise ValueError("team channel config cannot be empty")

        token = channel.config.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("bot token cannot be empty for team channel")

        self._team_id: str = channel.team_id
        self._channel_type: str = channel.channel_type
        self._token: str = clean_token_str(token)
        self._bot: Bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    @property
    def team_id(self) -> str:
        return self._team_id

    @property
    def channel_type(self) -> str:
        return self._channel_type

    @property
    def token(self) -> str:
        return self._token

    @property
    def bot(self) -> Bot:
        return self._bot
