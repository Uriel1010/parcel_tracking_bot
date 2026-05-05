from __future__ import annotations

from app.trackers.hfd import HfdTracker


class EpostTracker(HfdTracker):
    source_name = "epost"
    display_name = "ePost"
