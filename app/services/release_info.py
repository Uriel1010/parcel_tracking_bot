from __future__ import annotations

from pathlib import Path

from app import __version__


CHANGELOG_PATH = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def current_version() -> str:
    return __version__


def recent_changelog(max_chars: int = 3500, changelog_path: Path = CHANGELOG_PATH) -> str:
    text = changelog_path.read_text(encoding="utf-8")
    sections = _released_sections(text)
    if not sections:
        return ""

    selected: list[str] = []
    current_length = 0
    for section in sections:
        section_length = len(section) + (2 if selected else 0)
        if selected and current_length + section_length > max_chars:
            break
        selected.append(section)
        current_length += section_length
        if current_length >= max_chars:
            break
    result = "\n\n".join(selected).strip()
    return result[:max_chars].rstrip()


def _released_sections(text: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    in_release = False

    for line in text.splitlines():
        if line.startswith("## ["):
            if current and _has_content(current):
                sections.append("\n".join(current).strip())
            current = [line]
            in_release = not line.startswith("## [Unreleased]")
            continue
        if in_release:
            current.append(line)

    if current and _has_content(current):
        sections.append("\n".join(current).strip())
    return sections


def _has_content(lines: list[str]) -> bool:
    return any(line.strip().startswith(("-", "###")) for line in lines[1:])
