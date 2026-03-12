# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and this project uses a simple semantic-versioning style.

## [Unreleased]

## [0.1.0] - 2026-03-12

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
- Tracking now prefers Israel Post as the authoritative source for direct postal numbers and filters merged histories to dated events when timestamps are available.
- Event persistence now updates existing normalized events in place and removes stale event rows during refreshes.
- Status-change notifications now suppress tracker error details and avoid duplicate alerts for the same already-notified status fingerprint.

### Fixed
- Tracking heuristics were expanded for common international postal formats.
- Inline language switching and settings callbacks were stabilized.
- Parcel last-update and event timestamp rendering were corrected.
- Tracker adapters now clear transient error state after successful responses, and Israel Post parsing skips placeholder "no information" statuses.
