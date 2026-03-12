from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)
IGNORED_STATUS_TEXTS = {
    "",
    ".",
    "אין מידע",
    "no information",
    "information unavailable",
}


class IsraelPostTracker(BaseTracker):
    source_name = "israel_post"
    API_BASE_URL = "https://apimftprd.israelpost.co.il"
    TRACKING_ENDPOINT = "/MyPost-itemtrace/items/{tracking_number}/{lang}"
    JSON_HINT_URL = "https://mypost.israelpost.co.il/itemtrace"
    ENGLISH_URL = "https://israelpost.co.il/en/itemtrace"
    SUBSCRIPTION_KEY = "5ccb5b137e7444d885be752eda7f767a"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Ocp-Apim-Subscription-Key": self.SUBSCRIPTION_KEY,
        }
        events: list[TrackingEvent] = []
        errors: list[str] = []

        for lang in ("heb", "eng"):
            try:
                response = await self.client.get(
                    f"{self.API_BASE_URL}{self.TRACKING_ENDPOINT.format(tracking_number=tracking_number, lang=lang)}",
                    headers=headers,
                )
                response.raise_for_status()
                events = self._parse_api_json(response.text)
                if events:
                    errors = []
                    break
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Israel Post API request failed: %s", exc)
                errors.append(f"Israel Post temporary error: {exc}")

        urls = [
            (self.JSON_HINT_URL, {"itemcode": tracking_number}),
            (self.ENGLISH_URL, {"itemcode": tracking_number}),
        ]
        for url, params in urls:
            if events:
                break
            try:
                response = await self.client.get(url, params=params, headers=headers)
                response.raise_for_status()
                events = self._parse_content(response.text)
                if events:
                    errors = []
                    break
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Israel Post request failed: %s", exc)
                errors.append(f"Israel Post temporary error: {exc}")

        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=events[-1].status_code if events else "unknown",
            current_source=self.source_name,
            events=events,
            source_summaries={"israel_post": {"event_count": len(events)}},
            errors=errors,
        )

    def _parse_api_json(self, text: str) -> list[TrackingEvent]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        rows = []
        for row in data.get("Maslul") or []:
            if not isinstance(row, dict):
                continue
            location_parts = [str(row.get("BranchName") or "").strip(), str(row.get("City") or "").strip()]
            rows.append(
                {
                    "date": row.get("StatusDate"),
                    "status": row.get("Status") or row.get("CategoryName") or data.get("CategoryName") or "",
                    "category": row.get("CategoryName") or data.get("CategoryName") or "",
                    "location": ", ".join(part for part in location_parts if part),
                }
            )
        if not rows and data.get("CategoryName"):
            rows.append(
                {
                    "date": data.get("DeliveredDate"),
                    "status": data.get("StatusForDisplay") or data.get("CategoryName") or "",
                    "category": data.get("CategoryName") or "",
                    "location": data.get("DeliveryAddress") or data.get("SenderName") or "",
                }
            )
        return self._events_from_rows(rows)

    def _parse_content(self, text: str) -> list[TrackingEvent]:
        for parser in (self._parse_json_blob, self._parse_html):
            parsed = parser(text)
            if parsed:
                return parsed
        return []

    def _parse_json_blob(self, text: str) -> list[TrackingEvent]:
        matches = re.findall(r"<script[^>]*type=\"application/ld\\+json\"[^>]*>(.*?)</script>", text, re.S)
        for raw in matches:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and isinstance(data.get("track"), list):
                return self._events_from_rows(data["track"])

        generic_match = re.search(r"(\[\s*\{.*?tracking.*?\}\s*\])", text, re.I | re.S)
        if generic_match:
            try:
                data = json.loads(generic_match.group(1))
            except json.JSONDecodeError:
                return []
            return self._events_from_rows(data)
        return []

    def _parse_html(self, html: str) -> list[TrackingEvent]:
        soup = BeautifulSoup(html, "lxml")
        rows: list[dict[str, str]] = []
        for row in soup.select("table tr, .track-item, .tracking-row, .shipment-row, .item-row"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td, th, span, div")]
            text = " ".join(part for part in cells if part).strip()
            if not text:
                continue
            date_candidate = cells[0] if cells else ""
            status_candidate = cells[1] if len(cells) > 1 else text
            location_candidate = cells[2] if len(cells) > 2 else ""
            rows.append({"date": date_candidate, "status": status_candidate, "location": location_candidate})
        return self._events_from_rows(rows)

    def _events_from_rows(self, rows: list[dict]) -> list[TrackingEvent]:
        events: list[TrackingEvent] = []
        for row in rows:
            status_text = str(row.get("status") or row.get("description") or row.get("text") or "").strip()
            category_text = str(row.get("category") or "").strip()
            if not status_text:
                continue
            normalized_status = status_text.casefold()
            normalized_category = category_text.casefold()
            if normalized_status in IGNORED_STATUS_TEXTS and normalized_category in IGNORED_STATUS_TEXTS:
                continue
            combined_status_text = " | ".join(part for part in [category_text, status_text] if part)
            timestamp = parse_datetime(str(row.get("date") or row.get("eventDate") or row.get("timestamp") or ""))
            location = str(row.get("location") or row.get("place") or "").strip()
            if combined_status_text.casefold() in IGNORED_STATUS_TEXTS:
                continue
            events.append(
                TrackingEvent(
                    timestamp=timestamp,
                    status_code=normalize_status(combined_status_text or status_text),
                    status_text=combined_status_text or status_text,
                    location=location,
                    source=self.source_name,
                    raw_payload=json.dumps(row, ensure_ascii=False)[:500],
                )
            )
        events.sort(key=lambda event: event.timestamp or parse_datetime("1970-01-01") or event.timestamp)
        return events
