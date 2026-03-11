from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.bot.handlers_admin import router as admin_router
from app.bot.handlers_parcels import router as parcels_router
from app.bot.handlers_start import router as start_router
from app.config import Settings
from app.db import Database
from app.services.metadata_sync import initialize_bot_metadata
from app.services.notification_service import NotificationService
from app.services.parcel_service import ParcelService
from app.services.scheduler import SchedulerService
from app.utils.logging import configure_logging


async def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("starting_bot")

    db = Database(settings.database_path)
    await db.initialize()

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    await initialize_bot_metadata(bot, settings.bot_metadata_file_path, retries=settings.http_retry_count)
    dp = Dispatcher()
    parcel_service = ParcelService(db, settings)
    notification_service = NotificationService(db, bot, settings.stale_reminder_cooldown_days)
    scheduler = SchedulerService(
        db=db,
        bot=bot,
        parcel_service=parcel_service,
        notification_service=notification_service,
        refresh_interval_minutes=settings.refresh_interval_minutes,
        stale_check_interval_hours=settings.stale_check_interval_hours,
        stale_days=settings.stale_days,
    )

    dp["settings"] = settings
    dp["db"] = db
    dp["parcel_service"] = parcel_service
    dp.include_router(start_router)
    dp.include_router(parcels_router)
    dp.include_router(admin_router)

    scheduler.start()
    try:
        await dp.start_polling(bot, settings=settings, db=db, parcel_service=parcel_service)
    finally:
        await scheduler.stop()
        await parcel_service.close()
        with suppress(Exception):
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
