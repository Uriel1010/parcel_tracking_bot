from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TrackingEvent:
    timestamp: datetime | None
    status_code: str
    status_text: str
    location: str
    source: str
    raw_payload: str = ""


@dataclass(slots=True)
class TrackingSnapshot:
    tracking_number: str
    current_status: str
    current_source: str
    events: list[TrackingEvent] = field(default_factory=list)
    source_summaries: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParcelSummary:
    id: int
    tracking_number: str
    friendly_name: str | None
    current_status: str
    current_source: str | None
    last_event_at: datetime | None
    reminders_muted: bool
    archived: bool
