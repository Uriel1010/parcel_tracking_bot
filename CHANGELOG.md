# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and this project uses a simple semantic-versioning style.

## [Unreleased]

### Added
- Dockerized Telegram parcel tracking bot with SQLite persistence.
- Multi-user parcel tracking with inline-keyboard flows.
- Cainiao and Israel Post tracker adapters with merged normalized events.
- Status-change notifications, stale reminders, and delivered/archive handling.
- Admin Telegram dashboard and stats commands.
- Hebrew/English UI with per-user language selection.
- Startup synchronization for Telegram bot metadata from `bot_metadata.json`.
- Runtime-mounted Telegram metadata config for Docker deployments.

### Changed
- Israel Post integration now uses the public JSON endpoint used by the official frontend when available.
- Parcel timestamps are rendered in `Asia/Jerusalem` for user-facing views.
- Bulk parcel refresh runs concurrently for better responsiveness.

### Fixed
- Tracking heuristics were expanded for common international postal formats.
- Inline language switching and settings callbacks were stabilized.
- Parcel last-update and event timestamp rendering were corrected.
