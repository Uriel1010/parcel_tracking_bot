from datetime import UTC, datetime

from app.models import TrackingEvent, TrackingSnapshot
from app.trackers.merge import merge_snapshots


def test_merge_snapshots_deduplicates_and_prefers_latest_event() -> None:
    timestamp = datetime(2026, 3, 1, tzinfo=UTC)
    event_a = TrackingEvent(timestamp=timestamp, status_code="in_transit", status_text="Accepted", location="CN", source="cainiao")
    event_b = TrackingEvent(timestamp=timestamp, status_code="in_transit", status_text="Accepted", location="CN", source="cainiao")
    event_c = TrackingEvent(timestamp=datetime(2026, 3, 3, tzinfo=UTC), status_code="delivered", status_text="Delivered", location="IL", source="israel_post")
    merged = merge_snapshots(
        "LP123456789IL",
        [
            TrackingSnapshot(tracking_number="LP123456789IL", current_status="in_transit", current_source="cainiao", events=[event_a, event_b]),
            TrackingSnapshot(tracking_number="LP123456789IL", current_status="delivered", current_source="israel_post", events=[event_c]),
        ],
    )
    assert len(merged.events) == 2
    assert merged.current_status == "delivered"
