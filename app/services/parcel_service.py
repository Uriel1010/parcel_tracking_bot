from __future__ import annotations

import logging
import re
import asyncio
from typing import Any

import httpx

from app.config import Settings
from app.db import Database
from app.i18n import normalize_locale, status_label, t
from app.models import TrackingSnapshot
from app.services.parser_utils import (
    clean_tracking_number,
    event_fingerprint,
    is_hfd_tracking_number,
    is_reasonable_tracking_number,
    mask_phone_number,
    normalize_phone_number,
    snapshot_fingerprint,
)
from app.trackers.cainiao import CainiaoTracker
from app.trackers.exelot import ExelotTracker
from app.trackers.hfd import HfdTracker
from app.trackers.israel_post import IsraelPostTracker
from app.trackers.merge import merge_snapshots
from app.utils.time import days_since, format_datetime, format_datetime_from_iso, parse_iso, to_iso, utcnow


LOGGER = logging.getLogger(__name__)
UNIVERSAL_POSTAL_PATTERN = re.compile(r"^[A-Z]{2}\d{8,10}[A-Z]{1,2}$")
EXELOT_PATTERN = re.compile(r"^XLT\d{6,20}$")


class ParcelService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True)
        self.cainiao = CainiaoTracker(self.client)
        self.exelot = ExelotTracker(self.client)
        self.hfd = HfdTracker(self.client)
        self.israel_post = IsraelPostTracker(self.client)

    async def close(self) -> None:
        await self.client.aclose()

    async def ensure_user(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        language_code: str | None = None,
    ) -> int:
        return await self.db.upsert_user(
            telegram_user_id,
            username,
            first_name,
            normalize_locale(language_code),
            utcnow(),
        )

    async def get_user_locale(
        self,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        telegram_language_code: str | None = None,
    ) -> str:
        user = await self.db.get_user_by_telegram_id(telegram_user_id)
        if user:
            return normalize_locale(user.get("language_code"))
        await self.ensure_user(telegram_user_id, username, first_name, telegram_language_code)
        return normalize_locale(telegram_language_code)

    async def add_parcel_for_user(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        raw_tracking_number: str,
        friendly_name: str | None = None,
        hfd_phone_number: str | None = None,
        locale: str = "en",
    ) -> tuple[dict[str, Any] | None, str]:
        tracking_number = clean_tracking_number(raw_tracking_number)
        if not is_reasonable_tracking_number(tracking_number):
            return None, t(locale, "prompt.invalid_tracking")
        normalized_hfd_phone = None
        if is_hfd_tracking_number(tracking_number):
            normalized_hfd_phone = normalize_phone_number(hfd_phone_number)
            if normalized_hfd_phone is None:
                return None, t(locale, "prompt.invalid_hfd_phone")

        user_id = await self.ensure_user(telegram_user_id, username, first_name, locale)
        existing = await self.db.get_parcel_by_user_tracking(user_id, tracking_number)
        if existing:
            return existing, t(locale, "parcel.duplicate")

        normalized_name = self.normalize_friendly_name(friendly_name)
        parcel_id = await self.db.create_parcel(
            user_id,
            tracking_number,
            utcnow(),
            friendly_name=normalized_name,
            hfd_phone_number=normalized_hfd_phone,
        )
        parcel = await self.db.get_parcel_by_id(parcel_id)
        assert parcel is not None
        try:
            await self.refresh_parcel(parcel_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Initial refresh failed for %s", tracking_number)
            await self.db.update_notification_state(parcel_id, last_error_at=utcnow(), last_error_message=str(exc))
        return await self.db.get_parcel_by_id(parcel_id), t(locale, "parcel.added")

    def normalize_friendly_name(self, friendly_name: str | None) -> str | None:
        if friendly_name is None:
            return None
        cleaned = " ".join(friendly_name.strip().split())
        if not cleaned:
            return None
        return cleaned[:80]

    def normalize_hfd_phone_number(self, phone_number: str | None) -> str | None:
        return normalize_phone_number(phone_number)

    async def rename_parcel(self, parcel_id: int, friendly_name: str | None) -> dict[str, Any]:
        await self.db.set_friendly_name(parcel_id, self.normalize_friendly_name(friendly_name))
        parcel = await self.db.get_parcel_by_id(parcel_id)
        if parcel is None:
            raise ValueError("Parcel not found")
        return parcel

    async def set_hfd_phone_number(self, parcel_id: int, phone_number: str | None) -> dict[str, Any]:
        normalized = self.normalize_hfd_phone_number(phone_number)
        if normalized is None:
            raise ValueError("Invalid HFD phone number")
        await self.db.set_hfd_phone_number(parcel_id, normalized)
        try:
            return await self.refresh_parcel(parcel_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Refresh after HFD phone update failed for parcel_id=%s", parcel_id)
            await self.db.update_notification_state(parcel_id, last_error_at=utcnow(), last_error_message=str(exc))
            parcel = await self.db.get_parcel_by_id(parcel_id)
            if parcel is None:
                raise ValueError("Parcel not found") from exc
            return parcel

    async def refresh_parcel(self, parcel_id: int) -> dict[str, Any]:
        parcel = await self.db.get_parcel_by_id(parcel_id)
        if parcel is None:
            raise ValueError("Parcel not found")
        snapshot = await self.fetch_tracking_snapshot_for_parcel(parcel)
        await self.persist_snapshot(parcel_id, snapshot)
        return (await self.db.get_parcel_by_id(parcel_id)) or parcel

    async def refresh_all_user_parcels(self, telegram_user_id: int) -> int:
        parcels = await self.db.list_parcels_for_user(telegram_user_id, limit=500, offset=0)
        active_parcels = [parcel for parcel in parcels if not parcel["archived"]]
        if not active_parcels:
            return 0

        semaphore = asyncio.Semaphore(4)

        async def _refresh(parcel_id: int) -> bool:
            async with semaphore:
                try:
                    await self.refresh_parcel(parcel_id)
                    return True
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Bulk refresh failed for parcel_id=%s", parcel_id)
                    return False

        results = await asyncio.gather(*[_refresh(parcel["id"]) for parcel in active_parcels])
        return sum(1 for result in results if result)

    async def fetch_tracking_snapshot_for_parcel(self, parcel: dict[str, Any]) -> TrackingSnapshot:
        tracking_number = parcel["tracking_number"]
        if is_hfd_tracking_number(tracking_number):
            return await self.hfd.track(tracking_number, parcel.get("hfd_phone_number"))
        cainiao_snapshot = await self.cainiao.track(tracking_number)
        snapshots = [cainiao_snapshot]
        if EXELOT_PATTERN.match(tracking_number):
            snapshots.append(await self.exelot.track(tracking_number))
        israel_post_snapshot: TrackingSnapshot | None = None
        should_try_israel_post = (
            tracking_number.endswith("IL")
            or cainiao_snapshot.events
            or tracking_number.startswith(("LP", "SY", "UT", "CNG", "EE", "RR"))
            or bool(UNIVERSAL_POSTAL_PATTERN.match(tracking_number))
        )
        if should_try_israel_post:
            israel_post_snapshot = await self.israel_post.track(tracking_number)
            if israel_post_snapshot.events and (
                tracking_number.endswith("IL") or bool(UNIVERSAL_POSTAL_PATTERN.match(tracking_number))
            ):
                return merge_snapshots(tracking_number, [israel_post_snapshot])
            snapshots.append(israel_post_snapshot)
        return merge_snapshots(tracking_number, snapshots)

    async def persist_snapshot(self, parcel_id: int, snapshot: TrackingSnapshot) -> None:
        now = utcnow()
        event_rows = []
        for event in snapshot.events:
            event_rows.append(
                {
                    "event_fingerprint": event_fingerprint(event),
                    "event_timestamp": to_iso(event.timestamp),
                    "status_code": event.status_code,
                    "status_text": event.status_text,
                    "location": event.location,
                    "source": event.source,
                    "raw_payload": event.raw_payload,
                    "created_at": to_iso(now),
                }
            )
        await self.db.replace_events(parcel_id, event_rows)
        delivered_at = snapshot.events[-1].timestamp if snapshot.current_status == "delivered" and snapshot.events else None
        fingerprint = snapshot_fingerprint(snapshot.events, snapshot.current_status)
        last_event_at = snapshot.events[-1].timestamp if snapshot.events else None
        await self.db.update_parcel_snapshot(
            parcel_id,
            now=now,
            current_status=snapshot.current_status,
            current_source=snapshot.current_source,
            last_event_at=last_event_at,
            delivered_at=delivered_at,
            stale_reminder_sent_at=None,
            last_status_fingerprint=fingerprint,
            archived=True if snapshot.current_status == "delivered" else None,
        )
        if snapshot.errors:
            await self.db.update_notification_state(parcel_id, last_error_at=now, last_error_message="; ".join(snapshot.errors)[:500])
        else:
            await self.db.update_notification_state(parcel_id, clear_error=True)

    async def build_parcel_summary_text(self, parcel: dict[str, Any], locale: str) -> str:
        last_update = parse_iso(parcel["last_event_at"])
        days = days_since(last_update)
        if last_update is not None and days is not None:
            last_update_text = t(
                locale,
                "parcel.summary.last_update_at",
                date=format_datetime(last_update, locale=locale),
                days=days,
            )
        else:
            last_update_text = t(locale, "parcel.summary.last_update_none")
        title = parcel["friendly_name"] or parcel["tracking_number"]
        tracking_line = f"{parcel['tracking_number']}\n" if parcel.get("friendly_name") else ""
        return (
            f"<b>{title}</b>\n"
            f"{tracking_line}"
            f"{t(locale, 'parcel.details.status')}: <b>{status_label(locale, parcel['current_status'])}</b>\n"
            f"{t(locale, 'parcel.details.last_update')}: {last_update_text}\n"
            f"{t(locale, 'parcel.details.source')}: {parcel['current_source'] or status_label(locale, 'unknown')}"
        )

    async def build_parcel_details_text(self, parcel: dict[str, Any], locale: str, include_errors: bool = True) -> str:
        events = await self.db.list_parcel_events(parcel["id"], limit=5)
        notification_state = await self.db.get_notification_state(parcel["id"])
        last_event_at = parse_iso(parcel["last_event_at"])
        days = days_since(last_event_at)
        if last_event_at is not None and days is not None:
            last_update_text = t(
                locale,
                "parcel.details.last_update_at",
                date=format_datetime(last_event_at, locale=locale),
                days=days,
            )
        else:
            last_update_text = t(locale, "parcel.details.days_na")
        event_lines = [
            f"- {format_datetime_from_iso(event['event_timestamp'], locale=locale) or 'unknown time'} | {event['status_text']} | {event['location'] or 'n/a'}"
            for event in events
        ]
        event_text = "\n".join(event_lines) if event_lines else t(locale, "parcel.details.events_none")
        error_text = ""
        if include_errors and notification_state and notification_state.get("last_error_message"):
            error_text = f"\n\n{t(locale, 'parcel.details.issue', message=notification_state['last_error_message'])}"
        hfd_phone_line = ""
        if is_hfd_tracking_number(parcel["tracking_number"]):
            hfd_phone_line = f"{t(locale, 'parcel.details.hfd_phone')}: {mask_phone_number(parcel.get('hfd_phone_number'))}\n"
        return (
            f"<b>{parcel['friendly_name'] or parcel['tracking_number']}</b>\n"
            f"{t(locale, 'parcel.details.tracking')}: <code>{parcel['tracking_number']}</code>\n"
            f"{t(locale, 'parcel.details.name')}: {parcel['friendly_name'] or t(locale, 'parcel.details.name_empty')}\n"
            f"{hfd_phone_line}"
            f"{t(locale, 'parcel.details.status')}: <b>{status_label(locale, parcel['current_status'])}</b>\n"
            f"{t(locale, 'parcel.details.last_update')}: {last_update_text}\n"
            f"{t(locale, 'parcel.details.source')}: {parcel['current_source'] or status_label(locale, 'unknown')}\n"
            f"{t(locale, 'parcel.details.reminders')}: {t(locale, 'parcel.details.reminders_muted') if parcel['reminders_muted'] else t(locale, 'parcel.details.reminders_enabled')}\n\n"
            f"<b>{t(locale, 'parcel.details.events')}</b>\n{event_text}{error_text}"
        )

    async def maybe_mark_keep_tracking(self, parcel_id: int) -> None:
        await self.db.set_archived(parcel_id, False)
        await self.db.set_reminders_muted(parcel_id, False)

    async def keep_for_history(self, parcel_id: int) -> None:
        await self.db.set_archived(parcel_id, True)

    async def maybe_delete_stale(self, parcel_id: int) -> None:
        await self.db.delete_parcel(parcel_id)

    async def list_due_stale_parcels(self) -> list[dict[str, Any]]:
        parcels = await self.db.list_active_parcels()
        due = []
        for parcel in parcels:
            last_event_at = parse_iso(parcel["last_event_at"])
            if parcel["current_status"] == "delivered":
                continue
            if days_since(last_event_at) is not None and days_since(last_event_at) >= self.settings.stale_days:
                due.append(parcel)
        return due

    async def parcel_has_changed(self, parcel_id: int, previous_fingerprint: str | None) -> tuple[bool, dict[str, Any]]:
        parcel = await self.db.get_parcel_by_id(parcel_id)
        if parcel is None:
            raise ValueError("Parcel not found")
        state = await self.db.get_notification_state(parcel_id)
        current_fingerprint = parcel["last_status_fingerprint"]
        last_notified_fingerprint = state["last_notified_fingerprint"] if state else None
        changed = bool(
            current_fingerprint
            and current_fingerprint != previous_fingerprint
            and current_fingerprint != last_notified_fingerprint
        )
        return changed, parcel

    async def create_status_change_message(self, parcel: dict[str, Any], locale: str) -> str:
        details = await self.build_parcel_details_text(parcel, locale, include_errors=False)
        return f"{t(locale, 'parcel.update_detected')}\n\n{details}"
