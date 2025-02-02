from os import getenv

from aiogram import Bot, Dispatcher

BASE_URL = getenv("TG_BASE_URL")
GOD_BOT_PATH = "/webhook/god"
GOD_BOT_TOKEN = getenv("TG_TOKEN_GOD_BOT")


async def on_startup(dispatcher: Dispatcher, bot: Bot):
    await bot.set_webhook(f"{BASE_URL}{GOD_BOT_PATH}")
