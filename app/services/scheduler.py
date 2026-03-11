from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import Database
from app.services.notification_service import NotificationService
from app.services.parcel_service import ParcelService
from app.utils.time import utcnow


LOGGER = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        db: Database,
        bot: Bot,
        parcel_service: ParcelService,
        notification_service: NotificationService,
        refresh_interval_minutes: int,
        stale_check_interval_hours: int,
        stale_days: int,
    ) -> None:
        self.db = db
        self.bot = bot
        self.parcel_service = parcel_service
        self.notification_service = notification_service
        self.refresh_interval_minutes = refresh_interval_minutes
        self.stale_check_interval_hours = stale_check_interval_hours
        self.stale_days = stale_days
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self.scheduler.add_job(self.refresh_active_parcels, "interval", minutes=self.refresh_interval_minutes, id="refresh_active_parcels")
        self.scheduler.add_job(self.send_stale_reminders, "interval", hours=self.stale_check_interval_hours, id="send_stale_reminders")
        self.scheduler.start()

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)

    async def refresh_active_parcels(self) -> None:
        try:
            parcels = await self.db.list_active_parcels()
            for parcel in parcels:
                previous_fingerprint = parcel["last_status_fingerprint"]
                refreshed = await self.parcel_service.refresh_parcel(parcel["id"])
                changed, updated = await self.parcel_service.parcel_has_changed(parcel["id"], previous_fingerprint)
                if changed:
                    message = await self.parcel_service.create_status_change_message(updated, parcel["language_code"])
                    await self.notification_service.send_status_change(
                        parcel["telegram_user_id"],
                        updated,
                        message,
                        updated["last_status_fingerprint"],
                    )
                if refreshed["current_status"] == "delivered":
                    await self.notification_service.maybe_send_delivered(parcel["telegram_user_id"], refreshed, parcel["language_code"])
            await self.db.set_job_status("refresh_active_parcels", "ok", None, utcnow())
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("refresh_active_parcels failed")
            await self.db.set_job_status("refresh_active_parcels", "error", str(exc), utcnow())

    async def send_stale_reminders(self) -> None:
        try:
            parcels = await self.parcel_service.list_due_stale_parcels()
            for parcel in parcels:
                await self.notification_service.maybe_send_stale_reminder(
                    parcel["telegram_user_id"],
                    parcel,
                    self.stale_days,
                    parcel["language_code"],
                )
            await self.db.set_job_status("send_stale_reminders", "ok", None, utcnow())
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("send_stale_reminders failed")
            await self.db.set_job_status("send_stale_reminders", "error", str(exc), utcnow())
