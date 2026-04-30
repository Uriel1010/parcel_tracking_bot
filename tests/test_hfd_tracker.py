from app.trackers.hfd import HfdTracker


LOOKUP_OK = """<?xml version="1.0" encoding="utf-8"?>
<result><status>OK</status><status_message></status_message><ship_rand_num>64887367563787</ship_rand_num></result>
"""

LOOKUP_NOT_FOUND = """<?xml version="1.0" encoding="utf-8"?>
<result><status>NOT_FOUND</status><status_message>לא נמצאה התאמה בין מספר המשלוח ומספר הטלפון, נא לבדוק את הפרטים ולנסות שוב</status_message><ship_rand_num></ship_rand_num></result>
"""

DETAILS_HTML = """<!doctype html>
<html lang="en">
  <body>
    <table style="width:100%">
      <tr>
        <td class="td-ttl">תאריך</td>
        <td class="td-ttl">שעה</td>
        <td class="td-ttl">תאור</td>
      </tr>
      <tr>
        <td>16/04/26</td>
        <td>09:04</td>
        <td> מידע נקלט (משלוח עדיין לא הגיע) / shipment data received</td>
      </tr>
      <tr>
        <td>17/04/26</td>
        <td>10:15</td>
        <td> נמסר ללקוח / delivered</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parse_lookup_response() -> None:
    tracker = HfdTracker(None)
    assert tracker._parse_lookup_response(LOOKUP_OK) == ("OK", "", "64887367563787")


def test_parse_lookup_response_not_found() -> None:
    tracker = HfdTracker(None)
    status, message, ship_rand_num = tracker._parse_lookup_response(LOOKUP_NOT_FOUND)
    assert status == "NOT_FOUND"
    assert "לא נמצאה התאמה" in message
    assert ship_rand_num == ""


def test_parse_tracking_page() -> None:
    tracker = HfdTracker(None)
    events = tracker._parse_tracking_page(DETAILS_HTML)

    assert len(events) == 2
    assert events[0].status_code == "in_transit"
    assert events[0].status_text == "מידע נקלט (משלוח עדיין לא הגיע) / shipment data received"
    assert events[1].status_code == "delivered"
