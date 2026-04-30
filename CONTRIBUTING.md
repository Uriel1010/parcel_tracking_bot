# Contributing

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For the Docker flow:

```bash
docker compose up -d --build
docker compose logs -f bot
```

## Development notes

- Keep runtime configuration in environment variables or mounted JSON files.
- Do not commit real secrets to the repository.
- Keep tracker-specific scraping logic isolated under `app/trackers/`.
- Prefer small, testable service changes over handler-heavy logic.

## Before opening a change

```bash
python3 -m compileall app tests
pytest
```

If Docker-related files changed, also verify:

```bash
docker compose config
```

## Changelog

- Add notable user-facing or operational changes to [`CHANGELOG.md`](CHANGELOG.md).
