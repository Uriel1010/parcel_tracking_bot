from datetime import UTC, datetime

from app.trackers.gaash import GaashTracker


TRACKING_DATA = """
{
  "Statuses": [
    {
      "StatusTime": "2026-05-08T10:15:40",
      "StatusCode": 1001,
      "StatusDescription": "Parcel is on the way to destination country",
      "Country": "IL",
      "TimeZoneOffset": "GMT+03:00"
    }
  ],
  "TrackingNumber": "GAIH50801543"
}
"""


def test_parse_tracking_data() -> None:
    tracker = GaashTracker(None)
    events = tracker._parse_tracking_data(TRACKING_DATA)

    assert len(events) == 1
    assert events[0].timestamp == datetime(2026, 5, 8, 7, 15, 40, tzinfo=UTC)
    assert events[0].status_code == "in_transit"
    assert events[0].status_text == "Parcel is on the way to destination country"
    assert events[0].location == "IL"
    assert events[0].source == "gaash"


def test_parse_nonce() -> None:
    html = 'var parcelStatusTrackerData = {"apiUrl":"https://gaashwd.com/wp-json/gaash-parcel-status-tracker/v1","nonce":"abc123"};'

    assert GaashTracker(None)._parse_nonce(html) == "abc123"
