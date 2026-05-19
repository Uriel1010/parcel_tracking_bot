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
    DETAIL_JSON_URL = "https://global.cainiao.com/global/detail.json"
    DETAIL_URL = "https://global.cainiao.com/detail.htm"
    NEW_DETAIL_URL = "https://global.cainiao.com/newDetail.htm"

    async def track(self, tracking_number: str) -> TrackingSnapshot:
        events: list[TrackingEvent] = []
        errors: list[str] = []
        headers = self._headers()

        try:
            response = await self.client.get(self.DETAIL_JSON_URL, params={"mailNos": tracking_number}, headers=headers)
            response.raise_for_status()
            if self._is_captcha_response(response.text):
                errors.append("Cainiao blocked the tracking request with a captcha challenge.")
            else:
                events = self._parse_json_response(response.text)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Cainiao JSON request failed: %s", exc)
            errors.append(f"Cainiao temporary error: {exc}")

        if events:
            errors = []
        else:
            page_events, page_errors = await self._track_detail_pages(tracking_number, headers)
            if page_events:
                events = page_events
                errors = []
            else:
                errors.extend(page_errors)

        current_status = events[-1].status_code if events else "unknown"
        return TrackingSnapshot(
            tracking_number=tracking_number,
            current_status=current_status,
            current_source=self.source_name,
            events=events,
            source_summaries={"cainiao": {"event_count": len(events)}},
            errors=list(dict.fromkeys(errors)),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://global.cainiao.com/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        }

    async def _track_detail_pages(self, tracking_number: str, headers: dict[str, str]) -> tuple[list[TrackingEvent], list[str]]:
        events: list[TrackingEvent] = []
        errors: list[str] = []

        for url in (self.NEW_DETAIL_URL, self.DETAIL_URL):
            try:
                response = await self.client.get(url, params={"mailNoList": tracking_number}, headers=headers)
                response.raise_for_status()
                if self._is_captcha_response(response.text):
                    errors.append("Cainiao blocked the tracking page with a captcha challenge.")
                    continue
                events = self._parse_content(response.text)
                if events:
                    break
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Cainiao request failed: %s", exc)
                errors.append(f"Cainiao temporary error: {exc}")
        return events, errors

    def _is_captcha_response(self, text: str) -> bool:
        lowered = text[:5000].casefold()
        return "captcha interception" in lowered or "punish-component" in lowered or "bxpunish" in lowered

    def _parse_json_response(self, text: str) -> list[TrackingEvent]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = data.get("data") or data.get("module") or data
        return self._events_from_json_data(data)

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
                    if key.lower() in {"section1", "origintrackinginfo", "destcitytrackinginfo", "eventlist", "progresspointlist"} and isinstance(value, list):
                        candidates.extend(v for v in value if isinstance(v, dict))
                    else:
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
        return self._events_from_candidate_dicts(candidates)

    def _events_from_json_data(self, data: object) -> list[TrackingEvent]:
        candidates: list[dict] = []
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                progress_points = item.get("progressPointList")
                if isinstance(progress_points, list):
                    candidates.extend(point for point in progress_points if isinstance(point, dict))
                stack.extend(item.values())
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
                or item.get("actionDesc")
                or item.get("eventDesc")
                or item.get("content")
                or item.get("title")
                or item.get("status")
                or ""
            ).strip()
            if not status_text:
                continue
            timestamp = parse_datetime(
                str(
                    item.get("time")
                    or item.get("timeStr")
                    or item.get("eventTime")
                    or item.get("eventDate")
                    or item.get("scanDate")
                    or item.get("gmtCreate")
                    or ""
                )
            )
            location = str(
                item.get("place")
                or item.get("pointName")
                or item.get("country")
                or item.get("countryName")
                or item.get("city")
                or item.get("location")
                or item.get("address")
                or ""
            ).strip()
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
