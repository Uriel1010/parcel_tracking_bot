from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    delta = utcnow() - dt.astimezone(UTC)
    return max(delta.days, 0)


def format_datetime(dt: datetime | None, locale: str = "en") -> str | None:
    if dt is None:
        return None
    localized = dt.astimezone(JERUSALEM_TZ)
    if locale.startswith("he"):
        return localized.strftime("%d.%m.%Y, %H:%M")
    return localized.strftime("%d %b %Y, %H:%M")


def format_datetime_from_iso(value: str | None, locale: str = "en") -> str | None:
    return format_datetime(parse_iso(value), locale=locale)
