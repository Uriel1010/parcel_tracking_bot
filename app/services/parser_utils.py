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
HFD_PATTERN = re.compile(r"^HD\d{6,20}$")


def clean_tracking_number(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def is_reasonable_tracking_number(value: str) -> bool:
    cleaned = clean_tracking_number(value)
    return 8 <= len(cleaned) <= 40 and any(ch.isdigit() for ch in cleaned)


def is_hfd_tracking_number(value: str) -> bool:
    return bool(HFD_PATTERN.match(clean_tracking_number(value)))


def normalize_phone_number(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if digits.startswith("972") and len(digits) in {11, 12}:
        digits = f"0{digits[3:]}"
    if len(digits) not in {9, 10} or not digits.startswith("0"):
        return None
    return digits


def mask_phone_number(value: str | None) -> str:
    if not value:
        return "-"
    normalized = normalize_phone_number(value) or value
    visible = normalized[-4:] if len(normalized) >= 4 else normalized
    return f"***{visible}"


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
        "%d/%m/%y %H:%M",
        "%d/%m/%Y",
        "%d/%m/%y",
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


def event_status_fingerprint(event: TrackingEvent) -> str:
    payload = "|".join(
        [
            event.timestamp.isoformat() if event.timestamp else "",
            event.status_code,
            event.source,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_fingerprint(events: list[TrackingEvent], current_status: str) -> str:
    latest = event_status_fingerprint(events[-1]) if events else ""
    semantic_count = len({event_status_fingerprint(event) for event in events})
    payload = f"{current_status}|{latest}|{semantic_count}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
