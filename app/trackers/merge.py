from __future__ import annotations

from app.models import TrackingEvent, TrackingSnapshot
from app.services.parser_utils import event_fingerprint


def merge_snapshots(tracking_number: str, snapshots: list[TrackingSnapshot]) -> TrackingSnapshot:
    merged: list[TrackingEvent] = []
    seen: set[str] = set()
    source_summaries: dict[str, object] = {}
    errors: list[str] = []

    for snapshot in snapshots:
        source_summaries.update(snapshot.source_summaries)
        errors.extend(snapshot.errors)
        for event in snapshot.events:
            fingerprint = event_fingerprint(event)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            merged.append(event)

    # Prefer dated events when at least one source provides real timestamps.
    if any(event.timestamp is not None for event in merged):
        merged = [event for event in merged if event.timestamp is not None]

    merged.sort(key=lambda event: (event.timestamp is None, event.timestamp))
    current_event = merged[-1] if merged else None

    return TrackingSnapshot(
        tracking_number=tracking_number,
        current_status=current_event.status_code if current_event else "unknown",
        current_source=current_event.source if current_event else "unknown",
        events=merged,
        source_summaries=source_summaries,
        errors=errors,
    )
