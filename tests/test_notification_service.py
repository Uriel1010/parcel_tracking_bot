from __future__ import annotations

import pytest

from app.services.notification_service import NotificationService


pytestmark = pytest.mark.asyncio


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})


class FakeDb:
    async def get_notification_state(self, parcel_id: int) -> dict | None:
        return None

    async def update_notification_state(self, parcel_id: int, **kwargs) -> None:
        return None

    async def update_parcel_snapshot(self, parcel_id: int, **kwargs) -> None:
        return None


def _parcel(tracking_number: str) -> dict:
    return {
        "id": 1,
        "tracking_number": tracking_number,
        "current_status": "in_transit",
        "current_source": "israel_post",
        "last_event_at": None,
        "delivered_at": None,
        "last_status_fingerprint": "fingerprint",
        "archived": False,
        "reminders_muted": False,
    }


async def test_delivered_notice_includes_tracking_hashtag() -> None:
    bot = FakeBot()
    service = NotificationService(FakeDb(), bot, stale_reminder_cooldown_days=7)  # type: ignore[arg-type]

    sent = await service.maybe_send_delivered(123, _parcel("ECSA0061337"), "en")

    assert sent is True
    assert bot.messages[0]["text"].endswith("\n\n#ECSA0061337")


async def test_stale_reminder_includes_tracking_hashtag() -> None:
    bot = FakeBot()
    service = NotificationService(FakeDb(), bot, stale_reminder_cooldown_days=7)  # type: ignore[arg-type]

    sent = await service.maybe_send_stale_reminder(123, _parcel("RS1303375696Y"), 14, "en")

    assert sent is True
    assert bot.messages[0]["text"].endswith("\n\n#RS1303375696Y")
