from app.trackers.israel_post import IsraelPostTracker


def test_events_from_rows_drops_placeholder_status_text() -> None:
    tracker = IsraelPostTracker(None)

    events = tracker._events_from_rows(
        [
            {
                "date": "2026-03-09 02:00",
                "category": "בתהליך מיון",
                "status": ".",
                "location": " מרכז המיון במודיעין, מודיעין - ",
            }
        ]
    )

    assert len(events) == 1
    assert events[0].status_text == "בתהליך מיון"
    assert events[0].location == "מרכז המיון במודיעין, מודיעין"
