from __future__ import annotations

import json
import logging

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class ExelotTracker(BaseTracker):
    source_name = "exelot"
    TRACKING_ENDPOINT = "https://apiv2p.exelot.com/api/v2/parcels/tracking/details/{tracking_number}"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://myparcel.exelot.com",
            "Referer": "https://myparcel.exelot.com/",
        }
        errors: list[str] = []
        events: list[TrackingEvent] = []

        try:
            response = await self.client.get(
                self.TRACKING_ENDPOINT.format(tracking_number=tracking_number),
                headers=headers,
            )
            response.raise_for_status()
            events = self._parse_payload(response.text)
            if events:
                errors = []
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Exelot request failed: %s", exc)
            errors.append(f"Exelot temporary error: {exc}")

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={"exelot": {"event_count": len(events)}},
            errors=errors,
        )

    def _parse_payload(self, text: str) -> list[TrackingEvent]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list) or not payload:
            return []

        item = payload[0]
        if not isinstance(item, dict):
            return []

        events: list[TrackingEvent] = []
        for row in item.get("statusHistory") or []:
            if not isinstance(row, dict):
                continue
            status_text = str(row.get("statusText") or "").strip()
            if not status_text:
                continue
            location = str(row.get("statusLocations") or "").strip()
            status_code_hint = str(row.get("statusCode") or "").strip()
            combined_text = " | ".join(part for part in [status_text, status_code_hint] if part)
            events.append(
                TrackingEvent(
                    timestamp=parse_datetime(str(row.get("date") or "")),
                    status_code=normalize_status(combined_text or status_text),
                    status_text=status_text,
                    location=location,
                    source=self.source_name,
                    raw_payload=json.dumps(row, ensure_ascii=False)[:500],
                )
            )

        events.sort(key=lambda event: (event.timestamp is None, event.timestamp))
        return events
