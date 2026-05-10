from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta, timezone

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class GaashTracker(BaseTracker):
    source_name = "gaash"
    HOME_URL = "https://gaashwd.com/"
    API_BASE_URL = "https://gaashwd.com/wp-json/gaash-parcel-status-tracker/v1"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        errors: list[str] = []
        events: list[TrackingEvent] = []
        try:
            nonce = await self._fetch_nonce()
            response = await self.client.get(
                f"{self.API_BASE_URL}/parcel-tracking-data",
                params={"parcel_id": tracking_number, "lang": "en"},
                headers=self._headers(nonce),
            )
            response.raise_for_status()
            events = self._parse_tracking_data(response.text)
            if not events:
                errors.append("GAASH returned no tracking events for this shipment.")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("GAASH tracking request failed: %s", exc)
            errors.append(f"GAASH temporary error: {exc}")

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={self.source_name: {"event_count": len(events)}},
            errors=errors,
        )

    async def _fetch_nonce(self) -> str:
        response = await self.client.get(self.HOME_URL, headers=self._headers())
        response.raise_for_status()
        nonce = self._parse_nonce(response.text)
        if not nonce:
            raise ValueError("Could not find GAASH tracking nonce.")
        return nonce

    def _parse_nonce(self, html: str) -> str:
        match = re.search(r'"nonce"\s*:\s*"([^"]+)"', html)
        return match.group(1) if match else ""

    def _headers(self, nonce: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Referer": self.HOME_URL,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        }
        if nonce:
            headers["X-WP-Nonce"] = nonce
        return headers

    def _parse_tracking_data(self, text: str) -> list[TrackingEvent]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        events: list[TrackingEvent] = []
        for item in data.get("Statuses") or []:
            if not isinstance(item, dict):
                continue
            status_text = str(item.get("StatusDescription") or "").strip()
            if not status_text:
                continue
            events.append(
                TrackingEvent(
                    timestamp=self._parse_status_time(item),
                    status_code=normalize_status(status_text),
                    status_text=status_text,
                    location=str(item.get("Country") or "").strip(),
                    source=self.source_name,
                    raw_payload=json.dumps(item, ensure_ascii=False)[:500],
                )
            )
        events.sort(key=lambda event: event.timestamp or datetime(1970, 1, 1, tzinfo=UTC))
        return events

    def _parse_status_time(self, item: dict) -> datetime | None:
        raw = str(item.get("StatusTime") or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        offset = self._parse_timezone_offset(str(item.get("TimeZoneOffset") or ""))
        if offset is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.replace(tzinfo=offset).astimezone(UTC)

    def _parse_timezone_offset(self, value: str) -> timezone | None:
        match = re.search(r"GMT([+-])(\d{2}):?(\d{2})?", value)
        if not match:
            return None
        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3) or "0")
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
