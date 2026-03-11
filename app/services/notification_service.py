from __future__ import annotations

from datetime import timedelta

from aiogram import Bot

from app.bot.keyboards import delivered_keyboard, stale_keyboard
from app.db import Database
from app.i18n import t
from app.utils.time import parse_iso, utcnow


class NotificationService:
    def __init__(self, db: Database, bot: Bot, stale_reminder_cooldown_days: int) -> None:
        self.db = db
        self.bot = bot
        self.stale_reminder_cooldown_days = stale_reminder_cooldown_days

    async def send_status_change(self, telegram_user_id: int, parcel: dict, message: str, fingerprint: str) -> None:
        await self.bot.send_message(telegram_user_id, message)
        await self.db.update_notification_state(parcel["id"], last_notified_fingerprint=fingerprint)

    async def maybe_send_delivered(self, telegram_user_id: int, parcel: dict, locale: str) -> bool:
        state = await self.db.get_notification_state(parcel["id"])
        if state and int(state["delivered_notice_sent"]):
            return False
        await self.bot.send_message(
            telegram_user_id,
            t(locale, "parcel.delivered_notice", tracking_number=parcel["tracking_number"]),
            parse_mode="HTML",
            reply_markup=delivered_keyboard(parcel["id"], locale),
        )
        await self.db.update_notification_state(parcel["id"], delivered_notice_sent=True)
        return True

    async def maybe_send_stale_reminder(self, telegram_user_id: int, parcel: dict, stale_days: int, locale: str) -> bool:
        state = await self.db.get_notification_state(parcel["id"])
        if parcel["reminders_muted"]:
            return False
        now = utcnow()
        if state and state.get("stale_cooldown_until"):
            cooldown_until = parse_iso(state["stale_cooldown_until"])
            if cooldown_until and cooldown_until > now:
                return False
        await self.bot.send_message(
            telegram_user_id,
            t(locale, "parcel.stale", tracking_number=parcel["tracking_number"], days=stale_days),
            parse_mode="HTML",
            reply_markup=stale_keyboard(parcel["id"], locale),
        )
        await self.db.update_notification_state(
            parcel["id"],
            stale_reminder_sent_at=now,
            stale_cooldown_until=now + timedelta(days=self.stale_reminder_cooldown_days),
        )
        await self.db.update_parcel_snapshot(
            parcel["id"],
            now=now,
            current_status=parcel["current_status"],
            current_source=parcel["current_source"],
            last_event_at=parse_iso(parcel["last_event_at"]),
            delivered_at=parse_iso(parcel["delivered_at"]),
            stale_reminder_sent_at=now,
            last_status_fingerprint=parcel["last_status_fingerprint"],
            archived=bool(parcel["archived"]),
        )
        return True
