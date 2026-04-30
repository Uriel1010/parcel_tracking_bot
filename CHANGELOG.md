# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and this project uses a simple semantic-versioning style.

## [Unreleased]

## [0.2.1] - 2026-04-30

### Changed
- Bot profile metadata now lists the supported tracking services: Israel Post, HFD, Exelot, and AliExpress/Cainiao-style parcels.
- Help text now explains which services are supported and notes that HFD requires the linked phone number.

## [0.2.0] - 2026-04-21

### Added
- HFD tracking support for `HD...` shipments using the linked phone number required by HFD's public tracking flow.
- Guided add flow for HFD parcels that asks for the linked phone number before the optional friendly name.
- Inline parcel-details action for updating the stored HFD phone number on existing HFD parcels.

### Changed
- Parcel storage now supports parcel-specific HFD phone numbers so scheduled refreshes can continue tracking HFD shipments without prompting again.
- Parcel details now show a masked linked HFD phone number for HFD shipments.
- Freeform `HD...` tracking input now redirects into the guided HFD add flow instead of attempting an incomplete direct add.

## [0.1.1] - 2026-03-14

### Changed
- Status-change fingerprints now ignore Israel Post localization flapping, preventing duplicate alerts when the same scan alternates between Hebrew and English or degraded placeholder text.

### Fixed
- Israel Post event parsing now strips placeholder status fragments such as `.` and normalizes noisy location spacing before persisting event text.

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
