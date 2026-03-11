# Parcel Tracking Telegram Bot

Lightweight production-style Telegram bot for tracking parcels with a focus on:

- Israel Post local delivery tracking
- Exelot parcel tracking
- Cainiao / AliExpress-style parcels
- Multi-user tracking with SQLite persistence
- Hebrew/English UI with per-user language switching
- Inline-keyboard driven UX
- Background refresh, change notifications, stale reminders, and admin commands

## What it does

Users can add tracking numbers, list their parcels, view merged event history, refresh on demand, mute reminders, and delete or keep completed parcels. The bot periodically refreshes active parcels, notifies users when the newest status changes, and sends a reminder when no new events were seen for 14 days.

## Telegram metadata sync

- The bot loads Telegram-managed public metadata from [`bot_metadata.json`](/home/uriel/Projects/parcel_tracking_bot/bot_metadata.json) on startup.
- On every container restart it compares the configured values with Telegram and only updates what changed.
- The current implementation synchronizes:
  - bot name
  - description
  - short description
  - command list
  - chat menu button
- The metadata file supports language variants and command scopes.
- The file is mounted into the container, so you can edit `bot_metadata.json` without rebuilding the image. A normal container restart is enough to apply changes.

## Languages and UX

- The bot UI is available in English and Hebrew.
- Each user can change language from the inline `Settings` screen.
- Telegram's user language is used as the initial default when it is `en` or `he`; otherwise the bot falls back to English.
- The selected language is stored in SQLite and reused after restarts.

## Tracking flow

1. The bot normalizes the tracking number and stores it per Telegram user.
2. It queries Cainiao first.
3. It queries Exelot for Exelot-style tracking numbers such as `XLT...`.
4. It then tries Israel Post for local delivery enrichment or direct Israel Post numbers.
5. Events are normalized into one internal schema:
   - `timestamp`
   - `status_code`
   - `status_text`
   - `location`
   - `source`
   - `raw_payload`
6. The merged event stream is deduplicated and sorted chronologically.
7. The newest normalized event becomes the current derived status.

## Stale reminders

- Active parcels are checked periodically.
- If a parcel has had no new events for `STALE_DAYS` days, the bot sends one reminder.
- After a reminder, the bot waits `STALE_REMINDER_COOLDOWN_DAYS` days before reminding again, unless new activity appears first.
- Users can mute reminders per parcel.

## Admin commands

Admin access is restricted to `ADMIN_CHAT_ID`.

- `/admin`
- `/stats`
- `/users`
- `/parcels`

The admin dashboard shows totals, active counts, delivered/archived counts, top users by parcel count, and recent tracker/job errors when present.

## Environment variables

- `TELEGRAM_BOT_TOKEN`
- `ADMIN_CHAT_ID`
- `DATABASE_PATH`
- `BOT_METADATA_FILE_PATH`
- `REFRESH_INTERVAL_MINUTES`
- `STALE_CHECK_INTERVAL_HOURS`
- `STALE_DAYS`
- `STALE_REMINDER_COOLDOWN_DAYS`
- `REQUEST_TIMEOUT_SECONDS`
- `HTTP_RETRY_COUNT`
- `LOG_LEVEL`
- `PAGE_SIZE`

The code reads configuration from environment variables. The real `.env` file is intentionally not committed and is ignored by git.

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f bot
```

Persistent data is stored in `./data`, including the SQLite database file.
The Telegram metadata config is read from `./bot_metadata.json` and mounted into the container at `/app/config/bot_metadata.json`.

## Safe git workflow

Tracked example files:

- [`.env.example`](/home/uriel/Projects/parcel_tracking_bot/.env.example)
- [`docker-compose.yml.example`](/home/uriel/Projects/parcel_tracking_bot/docker-compose.yml.example)

Local files you should create but not commit:

- `.env`

Recommended first-time setup:

```bash
cp .env.example .env
```

Then edit `.env` with your real bot token and other local values.

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m app.main
```

## Project structure

```text
app/
  main.py
  config.py
  db.py
  models.py
  trackers/
  bot/
  services/
  utils/
tests/
Dockerfile
docker-compose.yml
requirements.txt
```

## Limitations

- Tracking is scraping/public-page based, so upstream markup or request-flow changes can break adapters.
- Israel Post’s older JSON API appears unavailable for end users; the adapter therefore prefers public pages and parsing fallbacks.
- Cainiao pages may move data between embedded JSON and rendered HTML; the adapter is intentionally isolated so it can be updated later without touching bot logic.
- This build uses SQLite for a single bot container. For multiple bot replicas, a server database would be safer.

## Safer secret handling

1. Copy `.env.example` to `.env`.
2. Replace the token and admin chat ID values in `.env`.
3. Keep `.env` out of git. It is already ignored by [`.gitignore`](/home/uriel/Projects/parcel_tracking_bot/.gitignore).

## Updating Telegram bot metadata

1. Edit [`bot_metadata.json`](/home/uriel/Projects/parcel_tracking_bot/bot_metadata.json).
2. Restart the container:

```bash
docker compose restart bot
```

On startup, the bot will detect the change and sync Telegram metadata automatically.

## Files created

- Runtime and ops: `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`
- Core app: `app/config.py`, `app/db.py`, `app/models.py`, `app/main.py`
- Metadata sync: `app/services/metadata_sync.py`, `bot_metadata.json`
- Trackers: `app/trackers/base.py`, `app/trackers/cainiao.py`, `app/trackers/israel_post.py`, `app/trackers/merge.py`
- Bot UX: `app/bot/handlers_start.py`, `app/bot/handlers_parcels.py`, `app/bot/handlers_admin.py`, `app/bot/keyboards.py`, `app/bot/callbacks.py`
- Services and utilities: `app/services/parcel_service.py`, `app/services/notification_service.py`, `app/services/scheduler.py`, `app/services/parser_utils.py`, `app/utils/logging.py`, `app/utils/time.py`
- Tests: `tests/test_parser_utils.py`, `tests/test_merge.py`
