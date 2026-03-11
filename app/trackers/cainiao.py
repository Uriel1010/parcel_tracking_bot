from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import normalize_status, parse_datetime
from app.trackers.base import BaseTracker


LOGGER = logging.getLogger(__name__)


class CainiaoTracker(BaseTracker):
    source_name = "cainiao"
    DETAIL_URL = "https://global.cainiao.com/detail.htm"
    NEW_DETAIL_URL = "https://global.cainiao.com/newDetail.htm"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        events: list[TrackingEvent] = []
        errors: list[str] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        for url in (self.NEW_DETAIL_URL, self.DETAIL_URL):
            try:
                response = await self.client.get(url, params={"mailNoList": tracking_number}, headers=headers)
                response.raise_for_status()
                events = self._parse_content(response.text)
                if events:
                    break
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Cainiao request failed: %s", exc)
                errors.append(f"Cainiao temporary error: {exc}")

        current_status = events[-1].status_code if events else "unknown"
        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=current_status,
            current_source=self.source_name,
            events=events,
            source_summaries={"cainiao": {"event_count": len(events)}},
            errors=errors,
        )

    def _parse_content(self, html: str) -> list[TrackingEvent]:
        parsed = self._parse_json_blob(html)
        if parsed:
            return parsed
        return self._parse_html(html)

    def _parse_json_blob(self, html: str) -> list[TrackingEvent]:
        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", html, re.S)
        if not match:
            match = re.search(r"__NEXT_DATA__\"\s*type=\"application/json\">(.*?)</script>", html, re.S)
        if not match:
            return []
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        candidates: list[dict] = []
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    if key.lower() in {"section1", "origintrackinginfo", "destcitytrackinginfo", "eventlist"} and isinstance(value, list):
                        candidates.extend(v for v in value if isinstance(v, dict))
                    else:
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
        return self._events_from_candidate_dicts(candidates)

    def _parse_html(self, html: str) -> list[TrackingEvent]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[dict[str, str]] = []
        for item in soup.select(".waybill-path li, .tracking-detail li, .detail-list li, .route-item"):
            time_node = item.select_one(".time, .route-time, .cainiao-time")
            status_node = item.select_one(".info, .route-desc, .cainiao-desc, p, span")
            location_node = item.select_one(".place, .route-place, .cainiao-place")
            status_text = status_node.get_text(" ", strip=True) if status_node else item.get_text(" ", strip=True)
            if not status_text:
                continue
            candidates.append(
                {
                    "time": time_node.get_text(" ", strip=True) if time_node else "",
                    "desc": status_text,
                    "place": location_node.get_text(" ", strip=True) if location_node else "",
                }
            )
        return self._events_from_candidate_dicts(candidates)

    def _events_from_candidate_dicts(self, candidates: list[dict]) -> list[TrackingEvent]:
        events: list[TrackingEvent] = []
        for item in candidates:
            status_text = str(
                item.get("desc")
                or item.get("description")
                or item.get("statusDesc")
                or item.get("title")
                or item.get("status")
                or ""
            ).strip()
            if not status_text:
                continue
            timestamp = parse_datetime(
                str(item.get("time") or item.get("eventDate") or item.get("scanDate") or item.get("gmtCreate") or "")
            )
            location = str(item.get("place") or item.get("country") or item.get("location") or item.get("address") or "").strip()
            events.append(
                TrackingEvent(
                    timestamp=timestamp,
                    status_code=normalize_status(status_text),
                    status_text=status_text,
                    location=location,
                    source=self.source_name,
                    raw_payload=json.dumps(item, ensure_ascii=False)[:500],
                )
            )
        events.sort(key=lambda event: event.timestamp or parse_datetime("1970-01-01") or event.timestamp)
        return events
