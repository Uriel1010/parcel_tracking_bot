from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class TrackGlobalTracker(BaseTracker):
    source_name = "aliexpress_standard_shipping"
    AJAX_TRACK_URL = "https://track.global/en/ajax-track"
    REFERER_URL = "https://track.global/en/courier/cainiao"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        events: list[TrackingEvent] = []
        errors: list[str] = []
        headers = {
            "Accept": "text/html,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.REFERER_URL,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            response = await self.client.get(
                self.AJAX_TRACK_URL,
                params={"track": tracking_number, "not_frame": "1", "alias": ""},
                headers=headers,
            )
            response.raise_for_status()
            events = self._parse_tracking_widget(response.text)
            if not events:
                errors.append("Track.global returned no tracking events for this shipment.")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Track.global request failed: %s", exc)
            errors.append(f"Track.global temporary error: {exc}")

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={self.source_name: {"event_count": len(events)}},
            errors=errors,
        )

    def _parse_tracking_widget(self, html: str) -> list[TrackingEvent]:
        soup = BeautifulSoup(html, "lxml")
        events: list[TrackingEvent] = []
        for item in soup.select(".tracking-widget__list-item"):
            classes = item.get("class") or []
            if "tracking-widget__list-item_banner" in classes:
                continue
            status_node = item.select_one(".tracking-widget__list-text")
            if status_node is None:
                continue
            status_text = (status_node.get("data-original") or status_node.get_text(" ", strip=True)).strip()
            if not status_text:
                continue
            location, status_text = self._split_location(status_text)
            date_text = item.select_one(".tracking-widget__date")
            time_text = item.select_one(".tracking-widget__date-day")
            timestamp = parse_datetime(
                " ".join(
                    part
                    for part in [
                        date_text.get_text(" ", strip=True) if date_text else "",
                        time_text.get_text(" ", strip=True) if time_text else "",
                    ]
                    if part
                )
            )
            events.append(
                TrackingEvent(
                    timestamp=timestamp,
                    status_code=normalize_status(status_text),
                    status_text=status_text,
                    location=location,
                    source=self.source_name,
                    raw_payload=json.dumps(
                        {
                            "date": date_text.get_text(" ", strip=True) if date_text else "",
                            "time": time_text.get_text(" ", strip=True) if time_text else "",
                            "status": status_node.get("data-original") or status_node.get_text(" ", strip=True),
                        },
                        ensure_ascii=False,
                    )[:500],
                )
            )
        events.sort(key=lambda event: event.timestamp or parse_datetime("1970-01-01") or event.timestamp)
        return events

    def _split_location(self, status_text: str) -> tuple[str, str]:
        match = re.match(r"^\[(?P<location>[^\]]+)\]\s*(?P<status>.+)$", status_text)
        if not match:
            return "", status_text
        return match.group("location").strip(), match.group("status").strip()
