from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation

from integrations.tg_bot.handlers import create_router


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    dispatcher.include_router(create_router())
    return dispatcher


async def run_polling(token: str) -> None:
    async with Bot(token=token) as bot:
        await create_dispatcher().start_polling(bot, close_bot_session=False)
