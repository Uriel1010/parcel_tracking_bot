import json

from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands

from app.services.metadata_sync import (
    BotMetadataConfig,
    _commands_equal,
    load_bot_metadata_config,
)


def test_load_bot_metadata_config(tmp_path) -> None:
    metadata_path = tmp_path / "bot_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "name": {"default": "Parcel Tracking Bot", "by_language": {"he": "בוט מעקב חבילות"}},
                "description": "Track parcels",
                "short_description": "Parcel tracking",
                "commands": [
                    {
                        "commands": [
                            {"command": "start", "description": "Open the main menu"},
                            {"command": "help", "description": "Show help"},
                        ],
                        "scope": {"type": "default"},
                    }
                ],
                "menu_button": {"type": "commands"},
            }
        ),
        encoding="utf-8",
    )

    config = load_bot_metadata_config(str(metadata_path))

    assert isinstance(config, BotMetadataConfig)
    assert config.name[0].value == "Parcel Tracking Bot"
    assert config.name[1].language_code == "he"
    assert config.commands[0].scope == BotCommandScopeDefault()
    assert config.commands[0].commands[0] == BotCommand(command="start", description="Open the main menu")
    assert config.menu_button == MenuButtonCommands()


def test_commands_equal_detects_equal_and_changed_lists() -> None:
    local_commands = (
        BotCommand(command="start", description="Open the main menu"),
        BotCommand(command="help", description="Show help"),
    )
    same_remote = [
        BotCommand(command="start", description="Open the main menu"),
        BotCommand(command="help", description="Show help"),
    ]
    changed_remote = [
        BotCommand(command="start", description="Open the main menu"),
        BotCommand(command="help", description="Different"),
    ]

    assert _commands_equal(local_commands, same_remote) is True
    assert _commands_equal(local_commands, changed_remote) is False
