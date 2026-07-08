from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup
from httpx import HTTPStatusError, Response

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class Bar2GoTracker(BaseTracker):
    source_name = "bar2go"
    BASE_URL = "https://bar2go.co.il"
    ENDPOINTS = (
        ("/Tracking/GetTracking", "trackingNumber"),
        ("/Tracking/GetTrackingDetails", "trackingNumber"),
        ("/api/tracking", "trackingNumber"),
        ("/api/track", "trackingNumber"),
        ("/track", "trackingNumber"),
    )

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        events: list[TrackingEvent] = []
        errors: list[str] = []
        for path, param in self.ENDPOINTS:
            try:
                response = await self.client.get(
                    f"{self.BASE_URL}{path}",
                    params={param: tracking_number},
                    headers=self._headers(),
                )
                response.raise_for_status()
            except HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                LOGGER.warning("Bar2Go tracking endpoint failed: %s", exc)
                errors.append(f"Bar2Go temporary error: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Bar2Go tracking request failed: %s", exc)
                errors.append(f"Bar2Go temporary error: {exc}")
                continue

            events = self._parse_response(response)
            if events:
                break

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={self.source_name: {"event_count": len(events)}},
            errors=errors[:2],
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json,text/html,*/*",
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": self.BASE_URL,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        }

    def _parse_response(self, response: Response) -> list[TrackingEvent]:
        content_type = response.headers.get("content-type", "")
        text = response.text
        if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
            return self._parse_json(text)
        return self._parse_html(text)

    def _parse_json(self, text: str) -> list[TrackingEvent]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        events: list[TrackingEvent] = []
        for item in self._iter_event_dicts(data):
            event = self._event_from_mapping(item)
            if event:
                events.append(event)
        events.sort(key=lambda event: event.timestamp or parse_datetime("1970-01-01") or event.timestamp)
        return events

    def _iter_event_dicts(self, value: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if isinstance(value, dict):
            lowered_keys = {str(key).lower() for key in value}
            if lowered_keys & {"status", "statusdescription", "description", "event", "message"}:
                items.append(value)
            for nested in value.values():
                items.extend(self._iter_event_dicts(nested))
        elif isinstance(value, list):
            for nested in value:
                items.extend(self._iter_event_dicts(nested))
        return items

    def _event_from_mapping(self, item: dict[str, Any]) -> TrackingEvent | None:
        status_text = self._first_text(
            item,
            "StatusDescription",
            "statusDescription",
            "status",
            "Status",
            "description",
            "Description",
            "event",
            "message",
            "Message",
        )
        if not status_text:
            return None
        timestamp = parse_datetime(
            self._first_text(
                item,
                "date",
                "Date",
                "eventDate",
                "EventDate",
                "statusDate",
                "StatusDate",
                "createdAt",
                "CreatedAt",
            )
        )
        location = self._first_text(item, "location", "Location", "city", "City", "branch", "Branch")
        return TrackingEvent(
            timestamp=timestamp,
            status_code=normalize_status(status_text),
            status_text=status_text,
            location=location,
            source=self.source_name,
            raw_payload=json.dumps(item, ensure_ascii=False)[:500],
        )

    def _first_text(self, item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    def _parse_html(self, html: str) -> list[TrackingEvent]:
        soup = BeautifulSoup(html, "lxml")
        events: list[TrackingEvent] = []
        for row in soup.select("tr, .tracking-event, .tracking-row, .status-row"):
            text = row.get_text(" ", strip=True)
            if not text or "resource cannot be found" in text.lower():
                continue
            events.append(
                TrackingEvent(
                    timestamp=parse_datetime(text),
                    status_code=normalize_status(text),
                    status_text=text[:240],
                    location="",
                    source=self.source_name,
                    raw_payload=text[:500],
                )
            )
        return events
