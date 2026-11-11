import asyncio
import logging

from config import settings


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    token = settings.telegram_bot_token.strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN не задан. Добавьте токен в .env и запустите бот снова.")
        return 0

    from aiogram.utils.token import TokenValidationError

    from integrations.tg_bot.bot import run_polling

    logger = logging.getLogger(__name__)
    try:
        asyncio.run(run_polling(token))
    except KeyboardInterrupt:
        pass
    except TokenValidationError:
        logger.error("Некорректный формат TELEGRAM_BOT_TOKEN в .env.")
        return 1
    logger.info("Telegram-бот остановлен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
