from app.services.parser_utils import parse_datetime
from app.trackers.exelot import ExelotTracker


def test_parse_datetime_supports_exelot_format() -> None:
    parsed = parse_datetime("11 Mar 2026, 9:55 AM")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 3
    assert parsed.day == 11
    assert parsed.hour == 9
    assert parsed.minute == 55


def test_exelot_tracker_parses_status_history() -> None:
    tracker = ExelotTracker(client=None)  # type: ignore[arg-type]
    events = tracker._parse_payload(
        """
        [
          {
            "statusHistory": [
              {
                "date": "10 Mar 2026, 5:00 PM",
                "statusText": "Package landed in TLV Airport, IL",
                "statusCode": "45",
                "statusLocations": "Lod IL"
              },
              {
                "date": "11 Mar 2026, 9:55 AM",
                "statusText": "Package released from customs",
                "statusCode": "48",
                "statusLocations": "Lod IL"
              }
            ]
          }
        ]
        """
    )

    assert len(events) == 2
    assert events[-1].source == "exelot"
    assert events[-1].location == "Lod IL"
    assert events[-1].status_text == "Package released from customs"
    assert events[-1].status_code == "arrived_country"
