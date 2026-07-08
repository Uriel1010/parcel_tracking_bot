import httpx
import pytest

from app.services.parser_utils import is_bar2go_tracking_number
from app.trackers.bar2go import Bar2GoTracker


@pytest.mark.asyncio
async def test_bar2go_tracker_ignores_current_missing_routes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="The resource cannot be found.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await Bar2GoTracker(client).track("BR005681854MG")

    assert snapshot.current_status == "unknown"
    assert snapshot.current_source == "bar2go"
    assert snapshot.events == []
    assert snapshot.errors == []
    assert snapshot.source_summaries == {"bar2go": {"event_count": 0}}


@pytest.mark.asyncio
async def test_bar2go_tracker_parses_future_json_events() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/Tracking/GetTracking":
            return httpx.Response(
                200,
                json={
                    "events": [
                        {
                            "statusDescription": "Package received at Bar2Go hub",
                            "eventDate": "2026-07-08 12:30",
                            "location": "Tel Aviv",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await Bar2GoTracker(client).track("BR005681854MG")

    assert len(snapshot.events) == 1
    assert snapshot.current_status == "in_transit"
    assert snapshot.events[0].source == "bar2go"
    assert snapshot.events[0].location == "Tel Aviv"


def test_bar2go_tracking_number_detection() -> None:
    assert is_bar2go_tracking_number("BR005681854MG")
    assert not is_bar2go_tracking_number("BR005681854IL")
