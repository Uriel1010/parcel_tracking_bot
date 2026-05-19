from app.trackers.track_global import TrackGlobalTracker


TRACK_GLOBAL_HTML = """
<div class="tracking-widget__list">
  <div class="tracking-widget__list-item" role="listitem">
    <div class="tracking-widget__list-date">
      <span class="tracking-widget__date">May 6, 2026</span>
      <span class="tracking-widget__date-day">10:14</span>
    </div>
    <div class="tracking-widget__list-content">
      <span class="tracking-widget__list-text tracking-widget__translated" data-original="Arrived at departure transport hub">
        Arrived at departure transport hub
      </span>
    </div>
  </div>
  <div class="tracking-widget__list-item" role="listitem">
    <div class="tracking-widget__list-date">
      <span class="tracking-widget__date">May 6, 2026</span>
      <span class="tracking-widget__date-day">07:03</span>
    </div>
    <div class="tracking-widget__list-content">
      <span class="tracking-widget__list-text tracking-widget__translated" data-original="[Songgang Subdistrict] Departed from sorting center">
        [Songgang Subdistrict] Departed from sorting center
      </span>
    </div>
  </div>
  <div class="tracking-widget__list-item tracking-widget__list-item_banner" role="listitem">
    <span class="tracking-widget__list-text">Track in the app</span>
  </div>
  <div class="tracking-widget__list-item" role="listitem">
    <div class="tracking-widget__list-date">
      <span class="tracking-widget__date">May 5, 2026</span>
      <span class="tracking-widget__date-day">21:03</span>
    </div>
    <div class="tracking-widget__list-content">
      <span class="tracking-widget__list-text tracking-widget__translated" data-original="Received by logistics company">
        Received by logistics company
      </span>
    </div>
  </div>
</div>
"""


def test_parse_tracking_widget_skips_banners_and_sorts_events() -> None:
    tracker = TrackGlobalTracker(None)
    events = tracker._parse_tracking_widget(TRACK_GLOBAL_HTML)

    assert len(events) == 3
    assert events[0].status_text == "Received by logistics company"
    assert events[0].source == "aliexpress_standard_shipping"
    assert events[1].status_text == "Departed from sorting center"
    assert events[1].location == "Songgang Subdistrict"
    assert events[2].status_text == "Arrived at departure transport hub"


def test_parse_tracking_widget_ignores_no_information_placeholder() -> None:
    tracker = TrackGlobalTracker(None)
    events = tracker._parse_tracking_widget(
        """
        <div class="tracking-widget__list">
          <div class="tracking-widget__list-item" role="listitem">
            <span class="tracking-widget__list-text">No information available for this parcel</span>
          </div>
        </div>
        """
    )

    assert events == []
