from pathlib import Path

import pytest

from app.config import Settings
from app.db import Database
from app.utils.time import utcnow


def test_settings_supports_admin_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("ADMIN_USER_IDS", "123456789,123456789")
    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)

    settings = Settings.from_env()

    assert settings.admin_user_ids == (123456789,)
    assert settings.is_admin(123456789)
    assert not settings.is_admin(1)


@pytest.mark.asyncio
async def test_admin_user_block_audit_broadcast_and_delete(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "bot.db"))
    await db.initialize()
    user_id = await db.upsert_user(12345, "tester", "Test", "en", utcnow())
    parcel_id = await db.create_parcel(user_id, "AB123456789CD", utcnow())

    assert await db.is_user_blocked(12345) is False
    await db.set_user_blocked(12345, True, 123456789, utcnow())
    assert await db.is_user_blocked(12345) is True
    assert await db.list_broadcast_recipients() == []
    assert await db.list_active_parcels() == []

    await db.add_audit_log(123456789, "user_block", utcnow(), "user", 12345)
    audit = await db.list_audit_log()
    assert audit[0]["action"] == "user_block"

    impact = await db.user_delete_impact(12345)
    assert impact["parcels"] == 1
    assert await db.delete_user_data(12345) is True
    assert await db.get_user_by_telegram_id(12345) is None
    assert await db.get_parcel_by_id(parcel_id) is None


def test_bot_metadata_registers_admin_commands_only_for_admin_chat() -> None:
    from app.services.metadata_sync import load_bot_metadata_config

    config = load_bot_metadata_config("bot_metadata.json")
    chat_sets = [item for item in config.commands if getattr(item.scope, "type", "") == "chat"]

    assert len(chat_sets) == 3
    assert {item.scope.chat_id for item in chat_sets} == {123456789}
    assert all(any(command.command == "admin" for command in item.commands) for item in chat_sets)
