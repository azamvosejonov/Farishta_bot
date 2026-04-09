import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.config import BOT_TOKEN
from app.database.engine import engine
from app.database.models import Base
from app.handlers.user import router as user_router
from app.handlers.booking import router as booking_router
from app.handlers.admin import router as admin_router


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrate existing DB: add missing columns/tables
    from sqlalchemy import text
    async with engine.begin() as conn:
        # apartments: installment columns
        for col, col_def in [
            ("installment_available", "BOOLEAN DEFAULT FALSE"),
            ("initial_payment_percent", "FLOAT DEFAULT 30.0"),
            ("installment_months", "INTEGER DEFAULT 12"),
        ]:
            try:
                await conn.execute(text(
                    f"ALTER TABLE apartments ADD COLUMN IF NOT EXISTS {col} {col_def}"
                ))
            except Exception:
                pass

    logging.info("Database tables created")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(booking_router)
    dp.include_router(user_router)

    await on_startup()

    logging.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
