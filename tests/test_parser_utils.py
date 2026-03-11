from datetime import UTC, datetime, timedelta

from app.models import TrackingEvent
from app.services.parser_utils import clean_tracking_number, event_fingerprint, normalize_status, snapshot_fingerprint
from app.utils.time import format_datetime


def test_clean_tracking_number() -> None:
    assert clean_tracking_number(" lp 123-456 il ") == "LP123456IL"


def test_normalize_status() -> None:
    assert normalize_status("Out for delivery") == "out_for_delivery"
    assert normalize_status("Item delivered successfully") == "delivered"


def test_event_fingerprint_changes_with_payload() -> None:
    first = TrackingEvent(
        timestamp=datetime.now(tz=UTC),
        status_code="in_transit",
        status_text="Accepted",
        location="Shenzhen",
        source="cainiao",
    )
    second = TrackingEvent(
        timestamp=first.timestamp + timedelta(minutes=1),
        status_code="in_transit",
        status_text="Accepted",
        location="Shenzhen",
        source="cainiao",
    )
    assert event_fingerprint(first) != event_fingerprint(second)


def test_snapshot_fingerprint_changes_with_latest_event() -> None:
    first = TrackingEvent(
        timestamp=datetime.now(tz=UTC),
        status_code="in_transit",
        status_text="Accepted",
        location="Shenzhen",
        source="cainiao",
    )
    second = TrackingEvent(
        timestamp=first.timestamp,
        status_code="delivered",
        status_text="Delivered",
        location="Tel Aviv",
        source="israel_post",
    )
    assert snapshot_fingerprint([first], "in_transit") != snapshot_fingerprint([first, second], "delivered")


def test_format_datetime_uses_jerusalem_time() -> None:
    timestamp = datetime(2026, 3, 11, 12, 30, tzinfo=UTC)
    assert format_datetime(timestamp, locale="en") == "11 Mar 2026, 14:30"
    assert format_datetime(timestamp, locale="he") == "11.03.2026, 14:30"
