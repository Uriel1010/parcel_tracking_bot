from app.trackers.cainiao import CainiaoTracker


CAINIAO_DETAIL_JSON = """
{
  "data": [
    {
      "mailNo": "BR005040600MG",
      "processInfo": {
        "progressPointList": [
          {
            "timeStr": "2026-05-17 08:20:00",
            "actionDesc": "Departed from departure country/region",
            "pointName": "CN"
          },
          {
            "timeStr": "2026-05-18 11:10:00",
            "actionDesc": "Arrived at destination country/region",
            "pointName": "IL"
          }
        ]
      }
    }
  ]
}
"""


def test_parse_official_detail_json_progress_points() -> None:
    tracker = CainiaoTracker(None)
    events = tracker._parse_json_response(CAINIAO_DETAIL_JSON)

    assert len(events) == 2
    assert events[0].status_text == "Departed from departure country/region"
    assert events[0].location == "CN"
    assert events[0].source == "cainiao"
    assert events[1].status_text == "Arrived at destination country/region"
    assert events[1].location == "IL"


def test_detects_cainiao_captcha_response() -> None:
    tracker = CainiaoTracker(None)

    assert tracker._is_captcha_response("<title>Captcha Interception</title><punish-component />")
