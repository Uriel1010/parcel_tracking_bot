from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    admin_chat_id: int
    database_path: str = "/app/data/bot.db"
    bot_metadata_file_path: str = "/app/config/bot_metadata.json"
    refresh_interval_minutes: int = 45
    stale_check_interval_hours: int = 24
    stale_days: int = 14
    stale_reminder_cooldown_days: int = 7
    request_timeout_seconds: int = 20
    http_retry_count: int = 2
    log_level: str = "INFO"
    page_size: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        admin_chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
        if not admin_chat_id:
            raise RuntimeError("ADMIN_CHAT_ID is required")
        return cls(
            telegram_bot_token=token,
            admin_chat_id=int(admin_chat_id),
            database_path=os.getenv("DATABASE_PATH", "/app/data/bot.db"),
            bot_metadata_file_path=os.getenv("BOT_METADATA_FILE_PATH", "/app/config/bot_metadata.json"),
            refresh_interval_minutes=_get_int("REFRESH_INTERVAL_MINUTES", 45),
            stale_check_interval_hours=_get_int("STALE_CHECK_INTERVAL_HOURS", 24),
            stale_days=_get_int("STALE_DAYS", 14),
            stale_reminder_cooldown_days=_get_int("STALE_REMINDER_COOLDOWN_DAYS", 7),
            request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 20),
            http_retry_count=_get_int("HTTP_RETRY_COUNT", 2),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            page_size=_get_int("PAGE_SIZE", 5),
        )
