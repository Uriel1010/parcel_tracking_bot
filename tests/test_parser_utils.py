from datetime import UTC, datetime, timedelta

from app.models import TrackingEvent
from app.services.parser_utils import (
    append_tracking_hashtag,
    clean_tracking_number,
    event_fingerprint,
    event_status_fingerprint,
    is_aliexpress_standard_tracking_number,
    is_epost_tracking_number,
    is_gaash_tracking_number,
    is_hfd_tracking_number,
    requires_linked_phone_number,
    mask_phone_number,
    normalize_phone_number,
    normalize_status,
    parse_datetime,
    snapshot_fingerprint,
    tracking_hashtag,
)
from app.utils.time import format_datetime


def test_clean_tracking_number() -> None:
    assert clean_tracking_number(" lp 123-456 il ") == "LP123456IL"


def test_tracking_hashtag_uses_normalized_tracking_number() -> None:
    assert tracking_hashtag(" rs 1303375696-y ") == "#RS1303375696Y"
    assert tracking_hashtag("ECSA0061337") == "#ECSA0061337"
    assert tracking_hashtag("HD001194524") == "#HD001194524"


def test_append_tracking_hashtag_adds_final_search_line() -> None:
    assert append_tracking_hashtag("Update message\n", " rs 1303375696-y ") == "Update message\n\n#RS1303375696Y"


def test_is_hfd_tracking_number() -> None:
    assert is_hfd_tracking_number("HD001194524")
    assert not is_hfd_tracking_number("RS1303375696Y")


def test_is_epost_tracking_number() -> None:
    assert is_epost_tracking_number("ECSA0061337")
    assert not is_epost_tracking_number("HD001194524")


def test_is_aliexpress_standard_tracking_number() -> None:
    assert is_aliexpress_standard_tracking_number("MB0181508216Y")
    assert not is_aliexpress_standard_tracking_number("RS1303375696Y")


def test_is_gaash_tracking_number() -> None:
    assert is_gaash_tracking_number("GAIH50801543")
    assert not is_gaash_tracking_number("MB0181508216Y")


def test_requires_linked_phone_number() -> None:
    assert requires_linked_phone_number("HD001194524")
    assert requires_linked_phone_number("ECSA0061337")
    assert not requires_linked_phone_number("RS1303375696Y")


def test_normalize_phone_number() -> None:
    assert normalize_phone_number("0545544290") == "0545544290"
    assert normalize_phone_number("+972545544290") == "0545544290"
    assert normalize_phone_number("123") is None


def test_mask_phone_number() -> None:
    assert mask_phone_number("0545544290") == "***4290"


def test_normalize_status() -> None:
    assert normalize_status("Out for delivery") == "out_for_delivery"
    assert normalize_status("Item delivered successfully") == "delivered"
    assert normalize_status("Departed from sorting center") == "in_transit"
    assert normalize_status("Arrived at departure transport hub") == "in_transit"
    assert normalize_status("Parcel is on the way to destination country") == "in_transit"


def test_parse_datetime_supports_two_digit_year() -> None:
    assert parse_datetime("16/04/26 09:04") == datetime(2026, 4, 16, 9, 4, tzinfo=UTC)


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


def test_event_status_fingerprint_ignores_localized_text_variants() -> None:
    timestamp = datetime(2026, 3, 11, 2, 0, tzinfo=UTC)
    hebrew = TrackingEvent(
        timestamp=timestamp,
        status_code="in_transit",
        status_text="בתהליך מיון | קליטה במודיעין",
        location="מרכז המיון במודיעין, מודיעין",
        source="israel_post",
    )
    english = TrackingEvent(
        timestamp=timestamp,
        status_code="in_transit",
        status_text="In sorting process | Received in Modiin",
        location="Modiin sorting center, Modiin",
        source="israel_post",
    )
    assert event_fingerprint(hebrew) != event_fingerprint(english)
    assert event_status_fingerprint(hebrew) == event_status_fingerprint(english)


def test_snapshot_fingerprint_ignores_localized_israel_post_flapping() -> None:
    timestamp = datetime(2026, 3, 11, 2, 0, tzinfo=UTC)
    hebrew = TrackingEvent(
        timestamp=timestamp,
        status_code="in_transit",
        status_text="אין מידע | הפריט נשלח",
        location="TEL-AVIV",
        source="israel_post",
    )
    english = TrackingEvent(
        timestamp=timestamp,
        status_code="in_transit",
        status_text="No information | Item sent",
        location="TEL-AVIV",
        source="israel_post",
    )
    assert snapshot_fingerprint([hebrew], "in_transit") == snapshot_fingerprint([english], "in_transit")


def test_format_datetime_uses_jerusalem_time() -> None:
    timestamp = datetime(2026, 3, 11, 12, 30, tzinfo=UTC)
    assert format_datetime(timestamp, locale="en") == "11 Mar 2026, 14:30"
    assert format_datetime(timestamp, locale="he") == "11.03.2026, 14:30"
