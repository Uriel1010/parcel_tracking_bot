from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from app.models import TrackingEvent


STATUS_MAP = {
    "delivered": "delivered",
    "received": "in_transit",
    "accepted": "in_transit",
    "processing": "in_transit",
    "forwarded": "in_transit",
    "delivery": "out_for_delivery",
    "out for delivery": "out_for_delivery",
    "arrived": "arrived_country",
    "destination": "arrived_country",
    "customs": "arrived_country",
    "transit": "in_transit",
    "accepted": "in_transit",
    "dispatch": "in_transit",
    "pickup": "in_transit",
    "failed": "exception",
    "exception": "exception",
    "return": "exception",
    "נקלט": "in_transit",
    "התקבל": "in_transit",
    "הועבר": "in_transit",
    "בדרך למסירה": "out_for_delivery",
    "נמסר": "delivered",
    "נמסרה": "delivered",
    "מסירה": "out_for_delivery",
    "ממתין": "arrived_country",
    "מיון": "in_transit",
}


def clean_tracking_number(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def is_reasonable_tracking_number(value: str) -> bool:
    cleaned = clean_tracking_number(value)
    return 8 <= len(cleaned) <= 40 and any(ch.isdigit() for ch in cleaned)


def normalize_status(text: str) -> str:
    lowered = text.lower().strip()
    for fragment, code in STATUS_MAP.items():
        if fragment in lowered:
            return code
    return "unknown"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d %b %Y, %I:%M %p",
        "%d %B %Y, %I:%M %p",
        "%d %b %Y %H:%M",
        "%d %B %Y %H:%M",
        "%b %d, %Y %H:%M",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def event_fingerprint(event: TrackingEvent) -> str:
    payload = "|".join(
        [
            event.timestamp.isoformat() if event.timestamp else "",
            event.status_code,
            event.status_text.strip(),
            event.location.strip(),
            event.source,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_fingerprint(events: list[TrackingEvent], current_status: str) -> str:
    latest = event_fingerprint(events[-1]) if events else ""
    payload = f"{current_status}|{latest}|{len(events)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
