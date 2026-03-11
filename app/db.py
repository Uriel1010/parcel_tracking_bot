from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import aiosqlite

from app.utils.time import parse_iso, to_iso


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    language_code TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS parcels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tracking_number TEXT NOT NULL,
                    friendly_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_status TEXT NOT NULL DEFAULT 'unknown',
                    current_source TEXT,
                    last_event_at TEXT,
                    last_checked_at TEXT,
                    delivered_at TEXT,
                    archived INTEGER NOT NULL DEFAULT 0,
                    reminders_muted INTEGER NOT NULL DEFAULT 0,
                    stale_reminder_sent_at TEXT,
                    last_status_fingerprint TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    UNIQUE(user_id, tracking_number)
                );

                CREATE TABLE IF NOT EXISTS parcel_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parcel_id INTEGER NOT NULL,
                    event_fingerprint TEXT NOT NULL,
                    event_timestamp TEXT,
                    status_code TEXT NOT NULL,
                    status_text TEXT NOT NULL,
                    location TEXT,
                    source TEXT NOT NULL,
                    raw_payload TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(parcel_id) REFERENCES parcels(id),
                    UNIQUE(parcel_id, event_fingerprint)
                );

                CREATE TABLE IF NOT EXISTS notification_state (
                    parcel_id INTEGER PRIMARY KEY,
                    last_notified_fingerprint TEXT,
                    stale_reminder_sent_at TEXT,
                    stale_cooldown_until TEXT,
                    delivered_notice_sent INTEGER NOT NULL DEFAULT 0,
                    last_error_at TEXT,
                    last_error_message TEXT,
                    FOREIGN KEY(parcel_id) REFERENCES parcels(id)
                );

                CREATE TABLE IF NOT EXISTS job_runs (
                    job_name TEXT PRIMARY KEY,
                    last_run_at TEXT,
                    last_status TEXT,
                    last_error TEXT
                );
                """
            )
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = {str(row[1]) for row in await cursor.fetchall()}
            if "language_code" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN language_code TEXT NOT NULL DEFAULT 'en'")
            await db.commit()

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(sql, params)
            await db.commit()

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def upsert_user(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        language_code: str,
        now: datetime,
    ) -> int:
        existing = await self.fetchone("SELECT id, language_code FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
        if existing:
            await self.execute(
                "UPDATE users SET username = ?, first_name = ?, language_code = ?, updated_at = ? WHERE id = ?",
                (username, first_name, language_code or existing["language_code"], to_iso(now), existing["id"]),
            )
            return int(existing["id"])

        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO users (telegram_user_id, username, first_name, language_code, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (telegram_user_id, username, first_name, language_code, to_iso(now), to_iso(now)),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM users WHERE telegram_user_id = ?", (telegram_user_id,))

    async def set_user_language(self, telegram_user_id: int, language_code: str) -> None:
        await self.execute("UPDATE users SET language_code = ? WHERE telegram_user_id = ?", (language_code, telegram_user_id))

    async def create_parcel(self, user_id: int, tracking_number: str, now: datetime, friendly_name: str | None = None) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO parcels (
                    user_id, tracking_number, friendly_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, tracking_number, friendly_name, to_iso(now), to_iso(now)),
            )
            await db.commit()
            parcel_id = int(cursor.lastrowid)
        await self.execute("INSERT OR IGNORE INTO notification_state(parcel_id) VALUES (?)", (parcel_id,))
        return parcel_id

    async def get_parcel_by_user_tracking(self, user_id: int, tracking_number: str) -> dict[str, Any] | None:
        return await self.fetchone(
            "SELECT * FROM parcels WHERE user_id = ? AND tracking_number = ?",
            (user_id, tracking_number),
        )

    async def get_parcel_for_user(self, parcel_id: int, telegram_user_id: int) -> dict[str, Any] | None:
        return await self.fetchone(
            """
            SELECT p.*, u.telegram_user_id, u.language_code
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            WHERE p.id = ? AND u.telegram_user_id = ?
            """,
            (parcel_id, telegram_user_id),
        )

    async def get_parcel_by_id(self, parcel_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM parcels WHERE id = ?", (parcel_id,))

    async def list_parcels_for_user(self, telegram_user_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT p.*, u.language_code
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            WHERE u.telegram_user_id = ?
            ORDER BY p.archived ASC, COALESCE(p.last_event_at, p.updated_at) DESC
            LIMIT ? OFFSET ?
            """,
            (telegram_user_id, limit, offset),
        )

    async def count_parcels_for_user(self, telegram_user_id: int) -> int:
        row = await self.fetchone(
            """
            SELECT COUNT(*) AS count
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            WHERE u.telegram_user_id = ?
            """,
            (telegram_user_id,),
        )
        return int(row["count"]) if row else 0

    async def list_active_parcels(self) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT p.*, u.telegram_user_id, u.language_code
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            WHERE p.archived = 0
            ORDER BY COALESCE(p.last_checked_at, p.updated_at) ASC
            """
        )

    async def list_parcel_events(self, parcel_id: int, limit: int = 5) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT *
            FROM parcel_events
            WHERE parcel_id = ?
            ORDER BY COALESCE(event_timestamp, created_at) DESC
            LIMIT ?
            """,
            (parcel_id, limit),
        )

    async def replace_events(self, parcel_id: int, events: list[dict[str, Any]]) -> None:
        async with aiosqlite.connect(self.path) as db:
            for event in events:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO parcel_events (
                        parcel_id, event_fingerprint, event_timestamp, status_code,
                        status_text, location, source, raw_payload, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        parcel_id,
                        event["event_fingerprint"],
                        event["event_timestamp"],
                        event["status_code"],
                        event["status_text"],
                        event["location"],
                        event["source"],
                        event["raw_payload"],
                        event["created_at"],
                    ),
                )
            await db.commit()

    async def update_parcel_snapshot(
        self,
        parcel_id: int,
        *,
        now: datetime,
        current_status: str,
        current_source: str | None,
        last_event_at: datetime | None,
        delivered_at: datetime | None,
        stale_reminder_sent_at: datetime | None,
        last_status_fingerprint: str | None,
        archived: bool | None = None,
    ) -> None:
        existing = await self.get_parcel_by_id(parcel_id)
        archived_value = existing["archived"] if existing and archived is None else int(bool(archived))
        delivered_value = existing["delivered_at"] if existing and delivered_at is None else to_iso(delivered_at)
        stale_value = existing["stale_reminder_sent_at"] if existing and stale_reminder_sent_at is None else to_iso(stale_reminder_sent_at)
        await self.execute(
            """
            UPDATE parcels
            SET updated_at = ?, current_status = ?, current_source = ?, last_event_at = ?,
                last_checked_at = ?, delivered_at = ?, stale_reminder_sent_at = ?,
                last_status_fingerprint = ?, archived = ?
            WHERE id = ?
            """,
            (
                to_iso(now),
                current_status,
                current_source,
                to_iso(last_event_at),
                to_iso(now),
                delivered_value,
                stale_value,
                last_status_fingerprint,
                archived_value,
                parcel_id,
            ),
        )

    async def set_reminders_muted(self, parcel_id: int, muted: bool) -> None:
        await self.execute("UPDATE parcels SET reminders_muted = ? WHERE id = ?", (int(muted), parcel_id))

    async def delete_parcel(self, parcel_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM parcel_events WHERE parcel_id = ?", (parcel_id,))
            await db.execute("DELETE FROM notification_state WHERE parcel_id = ?", (parcel_id,))
            await db.execute("DELETE FROM parcels WHERE id = ?", (parcel_id,))
            await db.commit()

    async def set_archived(self, parcel_id: int, archived: bool) -> None:
        await self.execute("UPDATE parcels SET archived = ? WHERE id = ?", (int(archived), parcel_id))

    async def set_friendly_name(self, parcel_id: int, friendly_name: str | None) -> None:
        await self.execute("UPDATE parcels SET friendly_name = ? WHERE id = ?", (friendly_name, parcel_id))

    async def update_notification_state(
        self,
        parcel_id: int,
        *,
        last_notified_fingerprint: str | None = None,
        stale_reminder_sent_at: datetime | None = None,
        stale_cooldown_until: datetime | None = None,
        delivered_notice_sent: bool | None = None,
        last_error_at: datetime | None = None,
        last_error_message: str | None = None,
        clear_error: bool = False,
    ) -> None:
        current = await self.fetchone("SELECT * FROM notification_state WHERE parcel_id = ?", (parcel_id,))
        if not current:
            await self.execute("INSERT INTO notification_state(parcel_id) VALUES (?)", (parcel_id,))
            current = await self.fetchone("SELECT * FROM notification_state WHERE parcel_id = ?", (parcel_id,))
        error_at_value = None if clear_error else (to_iso(last_error_at) if last_error_at is not None else current["last_error_at"])
        error_message_value = "" if clear_error else (last_error_message if last_error_message is not None else current["last_error_message"])
        await self.execute(
            """
            UPDATE notification_state
            SET last_notified_fingerprint = ?,
                stale_reminder_sent_at = ?,
                stale_cooldown_until = ?,
                delivered_notice_sent = ?,
                last_error_at = ?,
                last_error_message = ?
            WHERE parcel_id = ?
            """,
            (
                last_notified_fingerprint if last_notified_fingerprint is not None else current["last_notified_fingerprint"],
                to_iso(stale_reminder_sent_at) if stale_reminder_sent_at is not None else current["stale_reminder_sent_at"],
                to_iso(stale_cooldown_until) if stale_cooldown_until is not None else current["stale_cooldown_until"],
                int(delivered_notice_sent) if delivered_notice_sent is not None else current["delivered_notice_sent"],
                error_at_value,
                error_message_value,
                parcel_id,
            ),
        )

    async def get_notification_state(self, parcel_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM notification_state WHERE parcel_id = ?", (parcel_id,))

    async def set_job_status(self, job_name: str, status: str, error: str | None, now: datetime) -> None:
        await self.execute(
            """
            INSERT INTO job_runs(job_name, last_run_at, last_status, last_error)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_name) DO UPDATE SET
                last_run_at = excluded.last_run_at,
                last_status = excluded.last_status,
                last_error = excluded.last_error
            """,
            (job_name, to_iso(now), status, error),
        )

    async def get_stats(self) -> dict[str, Any]:
        stats = {}
        stats["users"] = int((await self.fetchone("SELECT COUNT(*) AS count FROM users"))["count"])
        stats["parcels"] = int((await self.fetchone("SELECT COUNT(*) AS count FROM parcels"))["count"])
        stats["active"] = int((await self.fetchone("SELECT COUNT(*) AS count FROM parcels WHERE archived = 0 AND current_status != 'delivered'"))["count"])
        stats["archived"] = int((await self.fetchone("SELECT COUNT(*) AS count FROM parcels WHERE archived = 1 OR current_status = 'delivered'"))["count"])
        stats["top_users"] = await self.fetchall(
            """
            SELECT u.telegram_user_id, u.username, COUNT(*) AS parcel_count
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            GROUP BY u.id
            ORDER BY parcel_count DESC, u.telegram_user_id ASC
            LIMIT 5
            """
        )
        stats["recent_errors"] = await self.fetchall(
            """
            SELECT parcel_id, last_error_at, last_error_message
            FROM notification_state
            WHERE last_error_at IS NOT NULL
            ORDER BY last_error_at DESC
            LIMIT 5
            """
        )
        return stats

    async def list_users(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT u.telegram_user_id, u.username, u.first_name, u.language_code, COUNT(p.id) AS parcel_count
            FROM users u
            LEFT JOIN parcels p ON p.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    async def list_recent_parcels(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT p.*, u.telegram_user_id
            FROM parcels p
            JOIN users u ON u.id = p.user_id
            ORDER BY p.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
