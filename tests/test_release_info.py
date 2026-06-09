from app.services.release_info import recent_changelog


def test_recent_changelog_skips_empty_unreleased_and_limits_sections(tmp_path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

## [Unreleased]

## [0.4.2] - 2026-05-19

### Added
- /version command.

## [0.4.1] - 2026-05-19

### Fixed
- Cainiao diagnostics.
""",
        encoding="utf-8",
    )

    result = recent_changelog(max_chars=80, changelog_path=changelog)

    assert "Unreleased" not in result
    assert "[0.4.2]" in result
    assert "/version command" in result
    assert "[0.4.1]" not in result
