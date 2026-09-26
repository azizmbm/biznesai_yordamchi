import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, business_plan, ai_assistant, subbot_products
import subbot_manager
from smm_scheduler import run_smm_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan!")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(business_plan.router)
    dp.include_router(ai_assistant.router)
    dp.include_router(subbot_products.router)

    subbot_manager.set_main_bot(bot)

    # Avval ro'yxatdan o'tgan sub-botlarni qayta ishga tushiramiz
    await subbot_manager.start_all_registered_subbots()

    # Fon vazifalar: SMM-plan kunlik yuborish
    asyncio.create_task(run_smm_scheduler(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
