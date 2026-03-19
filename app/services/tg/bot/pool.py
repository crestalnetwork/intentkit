import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    TokenBasedRequestHandler,
    setup_application,
)
from aiohttp import web
from aiohttp.web import Request

from intentkit.models.agent import Agent
from intentkit.models.team_channel import TeamChannel

from app.services.tg.bot.cache import (
    add_failed_agent,
    agent_by_id,
    bot_by_token,
    delete_cache_agent,
    delete_cache_bot,
    get_all_agent_bots,
    set_cache_agent,
    set_cache_bot,
)
from app.services.tg.bot.kind.god.router import god_router
from app.services.tg.bot.kind.god.startup import GOD_BOT_PATH, GOD_BOT_TOKEN, on_startup
from app.services.tg.bot.types.agent import BotPoolAgentItem
from app.services.tg.bot.types.bot import BotPoolItem
from app.services.tg.bot.types.kind import Kind
from app.services.tg.bot.types.router_obj import RouterObj
from app.services.tg.utils.cleanup import clean_token_str

logger = logging.getLogger(__name__)

BOTS_PATH = "/webhook/tgbot/{kind}/{bot_token}"


async def health_handler(request: Request):
    _ = request
    """Health check endpoint handler."""
    return web.json_response({"status": "healthy"})


class BotPool:
    app: web.Application
    base_url: str
    routers: dict[Kind, RouterObj]
    god_bot: Bot | None

    def __init__(self, base_url: str):
        from app.services.tg.bot.kind.ai_relayer.router import general_router
        from app.services.tg.bot.kind.team_channel.router import team_channel_router

        self.app = web.Application()
        _ = self.app.router.add_get("/health", health_handler)
        self.base_url = f"{base_url}{BOTS_PATH}"
        self.routers = {
            Kind.AiRelayer: RouterObj(general_router),
            Kind.TeamChannel: RouterObj(team_channel_router),
        }
        self.god_bot = None

    def init_god_bot(self):
        if GOD_BOT_TOKEN:
            try:
                logger.info("Initialize god bot...")
                self.god_bot = Bot(
                    token=GOD_BOT_TOKEN,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )
                storage = MemoryStorage()
                # In order to use RedisStorage you need to use Key Builder with bot ID:
                # storage = RedisStorage.from_url(TG_REDIS_DSN, key_builder=DefaultKeyBuilder(with_bot_id=True))
                dp = Dispatcher(storage=storage)
                _ = dp.include_router(god_router)
                dp.startup.register(on_startup)
                SimpleRequestHandler(dispatcher=dp, bot=self.god_bot).register(
                    self.app, path=GOD_BOT_PATH
                )
                setup_application(self.app, dp, bot=self.god_bot)
            except Exception as e:
                logger.error("failed to init god bot: %s", e)

    def init_all_dispatchers(self):
        logger.info("Initialize all dispatchers...")
        for kind, b in self.routers.items():
            storage = MemoryStorage()
            # In order to use RedisStorage you need to use Key Builder with bot ID:
            # storage = RedisStorage.from_url(TG_REDIS_DSN, key_builder=DefaultKeyBuilder(with_bot_id=True))
            b.set_dispatcher(Dispatcher(storage=storage))
            _ = b.get_dispatcher().include_router(b.get_router())
            TokenBasedRequestHandler(
                dispatcher=b.get_dispatcher(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            ).register(
                self.app,
                path=BOTS_PATH.format(kind=kind.value, bot_token="{bot_token}"),
            )
            setup_application(self.app, b.get_dispatcher())
            logger.info("%s router initialized...", kind)

    async def init_new_bot(self, agent: Agent):
        bot_item = None
        try:
            bot_item = BotPoolItem(agent)
            agent_item = BotPoolAgentItem(agent)

            _ = await bot_item.bot.delete_webhook(drop_pending_updates=True)
            _ = await bot_item.bot.set_webhook(
                self.base_url.format(kind=bot_item.kind, bot_token=bot_item.token)
            )

            set_cache_bot(bot_item)
            set_cache_agent(agent_item)

            logger.info("bot for agent %s initialized...", agent.id)

        except ValueError as e:
            logger.warning(
                "bot for agent %s did not started because of invalid data. err: %s",
                agent.id,
                e,
            )
        except TelegramUnauthorizedError as e:
            logger.info("failed to init new bot for agent %s: %s", agent.id, e)
            add_failed_agent(agent.id)
        except Exception as e:
            logger.info("failed to init new bot for agent %s: %s", agent.id, e)
        finally:
            if bot_item and bot_item.bot:
                await bot_item.bot.session.close()

    async def change_bot_token(self, agent: Agent):
        if not agent.telegram_entrypoint_enabled:
            old_agent_item = agent_by_id(agent.id)
            if old_agent_item:
                await self.stop_bot(agent.id, old_agent_item.bot_token)
            return

        new_bot_success = False
        old_bot_stopped = False
        new_bot_item = None
        old_bot = None

        try:
            if not agent.telegram_config:
                raise Exception(f"agent {agent.id} has no telegram config")

            new_token = agent.telegram_config.get("token")
            if not isinstance(new_token, str):
                raise Exception(f"agent {agent.id} has invalid telegram token")

            for _, v in get_all_agent_bots().items():
                if v.bot_token == new_token:
                    raise Exception(
                        f"there is an existing bot for agent {agent.id} with a duplicate token."
                    )

            new_bot_item = BotPoolItem(agent)
            new_agent_item = BotPoolAgentItem(agent)

            old_agent_item = agent_by_id(agent.id)
            if not old_agent_item:
                raise Exception(f"agent {agent.id} not found in pool to change token")

            old_cached_bot_item = bot_by_token(old_agent_item.bot_token)

            if old_cached_bot_item and old_cached_bot_item.bot:
                old_bot = old_cached_bot_item.bot
            else:
                old_bot = Bot(
                    token=old_agent_item.bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )

            await old_bot.session.close()
            _ = await old_bot.delete_webhook(drop_pending_updates=True)
            old_bot_stopped = True

            if not new_bot_item:
                raise ValueError("new_bot_item is None")

            _ = await new_bot_item.bot.delete_webhook(drop_pending_updates=True)
            _ = await new_bot_item.bot.set_webhook(
                self.base_url.format(
                    kind=str(new_bot_item.kind), bot_token=new_bot_item.token
                )
            )

            delete_cache_bot(old_agent_item.bot_token)
            set_cache_bot(new_bot_item)
            set_cache_agent(new_agent_item)

            logger.info("bot for agent %s token changed...", agent.id)
            new_bot_success = True
        except ValueError as e:
            logger.warning(
                f"bot for agent {agent.id} token did not changed because of invalid data. err: {e}"
            )
        except Exception as e:
            logger.error("failed to change bot token for agent %s: %s", agent.id, e)
        finally:
            if old_bot_stopped and old_bot:
                await old_bot.session.close()
            if not new_bot_success and new_bot_item and new_bot_item.bot:
                await new_bot_item.bot.session.close()

    async def stop_bot(self, agent_id: str, token: str | None):
        bot = None
        try:
            if token is None:
                logger.warning(
                    f"bot for agent {agent_id} token did not stopped because of empty token"
                )
                return

            cached_bot_item = bot_by_token(token)
            if cached_bot_item and cached_bot_item.bot:
                bot = cached_bot_item.bot
            else:
                bot = Bot(
                    token=token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )

            await bot.session.close()
            _ = await bot.delete_webhook(drop_pending_updates=True)

            delete_cache_bot(token)
            delete_cache_agent(agent_id)

            logger.info("Bot for agent %s stopped...", agent_id)
        except Exception as e:
            logger.error("failed to stop the bot for agent %s: %s", agent_id, e)
        finally:
            if bot:
                await bot.session.close()

    async def init_team_channel_bot(self, channel: TeamChannel):
        """Initialize a bot for a team channel."""
        from app.services.tg.bot.cache import (
            add_failed_team_channel,
            set_cache_team_channel_bot,
        )
        from app.services.tg.bot.types.team_channel import TeamChannelBotItem

        bot_item = None
        try:
            bot_item = TeamChannelBotItem(channel)

            _ = await bot_item.bot.delete_webhook(drop_pending_updates=True)
            _ = await bot_item.bot.set_webhook(
                self.base_url.format(kind="team_channel", bot_token=bot_item.token)
            )

            set_cache_team_channel_bot(bot_item)

            logger.info("Team channel bot for team %s initialized...", channel.team_id)

        except TelegramUnauthorizedError as e:
            logger.info(
                "Failed to init team channel bot for team %s: %s",
                channel.team_id,
                e,
            )
            add_failed_team_channel(f"team:{channel.team_id}")
        except Exception as e:
            logger.info(
                "Failed to init team channel bot for team %s: %s",
                channel.team_id,
                e,
            )
        finally:
            if bot_item and bot_item.bot:
                await bot_item.bot.session.close()

    async def stop_team_channel_bot(self, team_id: str, token: str):
        """Stop a team channel bot and remove from cache."""
        from app.services.tg.bot.cache import (
            delete_cache_team_channel_bot,
            team_channel_bot_by_token,
        )

        bot = None
        try:
            cached = team_channel_bot_by_token(token)
            if cached and cached.bot:
                bot = cached.bot
            else:
                bot = Bot(
                    token=token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )

            await bot.session.close()
            _ = await bot.delete_webhook(drop_pending_updates=True)

            delete_cache_team_channel_bot(token)
            logger.info("Team channel bot for team %s stopped...", team_id)
        except Exception as e:
            logger.error("Failed to stop team channel bot for team %s: %s", team_id, e)
        finally:
            if bot:
                await bot.session.close()

    async def modify_config(self, agent: Agent):
        old_agent_item = agent_by_id(agent.id)

        if not agent.telegram_config:
            raise Exception(f"agent {agent.id} has no telegram config")

        token = agent.telegram_config.get("token")
        if not isinstance(token, str):
            raise Exception(f"agent {agent.id} has invalid telegram token")

        if not old_agent_item or old_agent_item.bot_token != clean_token_str(token):
            raise Exception(
                f"illegal modification of agent configurations, the bot token for agent {agent.id} does not match existing token of the cache."
            )

        if not agent.telegram_entrypoint_enabled:
            await self.stop_bot(agent.id, token)
            return

        try:
            old_bot_item = bot_by_token(old_agent_item.bot_token)
            if old_bot_item:
                from typing import cast

                from app.services.tg.bot.types.bot import TelegramConfig

                old_bot_item.update_conf(
                    cast(TelegramConfig, cast(object, agent.telegram_config))
                )
            old_agent_item.updated_at = agent.deployed_at or agent.updated_at

            # if old_bot_item.kind != agent.telegram_config.get("kind"):
            #     await self.stop_bot(agent.id, token)
            #     await self.init_new_bot(agent)
            logger.info("configurations of the bot for agent %s updated...", agent.id)

        except ValueError as e:
            logger.warning(
                f"bot for agent {agent.id} config did not changed because of invalid data. err: {e}"
            )
        except Exception as e:
            logger.error(
                f"failed to change the configs of the bot for agent {agent.id}: {str(e)}"
            )

    async def start(self, asyncio_loop: Any, host: str, port: int):
        _ = asyncio_loop
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
