from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class HfdTracker(BaseTracker):
    source_name = "hfd"
    LOOKUP_URL = "https://api.hfd.co.il/rest/v3/api/ship-locate-num-and-phone"
    DETAILS_URL = "https://run.hfd.co.il/runcom.server/request.aspx"

    async def track(self, tracking_number: str, phone_number: str | None = None) -> TrackingSnapshot:
        if not phone_number:
            return TrackingSnapshot(
                tracking_number=tracking_number,
                current_status="unknown",
                current_source=self.source_name,
                events=[],
                source_summaries={"hfd": {"event_count": 0}},
                errors=["HFD requires a linked phone number for tracking."],
            )

        errors: list[str] = []
        events: list[TrackingEvent] = []
        try:
            lookup_response = await self.client.get(
                self.LOOKUP_URL,
                params={"num": tracking_number, "phone": phone_number},
                headers={"Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"},
            )
            lookup_response.raise_for_status()
            status, status_message, ship_rand_num = self._parse_lookup_response(lookup_response.text)
            if status != "OK" or not ship_rand_num:
                if status_message:
                    errors.append(f"HFD: {status_message}")
                else:
                    errors.append("HFD could not find this shipment for the provided phone number.")
            else:
                details_response = await self.client.get(
                    self.DETAILS_URL,
                    params={"APPNAME": "run", "PRGNAME": "ship_locate_random", "ARGUMENTS": f"-A{ship_rand_num}"},
                )
                details_response.raise_for_status()
                events = self._parse_tracking_page(details_response.text)
                if not events:
                    errors.append("HFD returned no tracking events for this shipment.")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("HFD tracking request failed: %s", exc)
            errors.append(f"HFD temporary error: {exc}")

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={"hfd": {"event_count": len(events)}},
            errors=errors,
        )

    def _parse_lookup_response(self, text: str) -> tuple[str, str, str]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return "ERROR", "Invalid HFD lookup response.", ""
        status = (root.findtext("status") or "").strip()
        status_message = (root.findtext("status_message") or "").strip()
        ship_rand_num = (root.findtext("ship_rand_num") or "").strip()
        return status, status_message, ship_rand_num

    def _parse_tracking_page(self, html: str) -> list[TrackingEvent]:
        soup = BeautifulSoup(html, "lxml")
        events: list[TrackingEvent] = []
        table = soup.find("table")
        if table is None:
            return events
        for row in table.find_all("tr")[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
            if len(cells) < 3:
                continue
            date_text, time_text, status_text = cells[:3]
            timestamp = parse_datetime(f"{date_text} {time_text}")
            cleaned_status = " ".join(status_text.split()).strip()
            if not cleaned_status:
                continue
            events.append(
                TrackingEvent(
                    timestamp=timestamp,
                    status_code=normalize_status(cleaned_status),
                    status_text=cleaned_status,
                    location="",
                    source=self.source_name,
                    raw_payload=" | ".join(cells)[:500],
                )
            )
        events.sort(key=lambda event: event.timestamp or parse_datetime("1970-01-01") or event.timestamp)
        return events
