from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatAdministrators,
    BotCommandScopeChatMember,
    BotCommandScopeDefault,
    MenuButtonCommands,
    MenuButtonDefault,
    MenuButtonWebApp,
    WebAppInfo,
)


LOGGER = logging.getLogger(__name__)

COMMAND_SCOPE_TYPES = {
    "default": BotCommandScopeDefault,
    "all_private_chats": BotCommandScopeAllPrivateChats,
    "all_group_chats": BotCommandScopeAllGroupChats,
    "all_chat_administrators": BotCommandScopeAllChatAdministrators,
    "chat": BotCommandScopeChat,
    "chat_administrators": BotCommandScopeChatAdministrators,
    "chat_member": BotCommandScopeChatMember,
}


@dataclass(frozen=True, slots=True)
class LocalizedValue:
    value: str
    language_code: str | None = None


@dataclass(frozen=True, slots=True)
class CommandSet:
    commands: tuple[BotCommand, ...]
    scope: Any
    language_code: str | None = None


@dataclass(frozen=True, slots=True)
class BotMetadataConfig:
    name: tuple[LocalizedValue, ...]
    description: tuple[LocalizedValue, ...]
    short_description: tuple[LocalizedValue, ...]
    commands: tuple[CommandSet, ...]
    menu_button: Any


def _normalize_localized_values(raw: Any, field_name: str) -> tuple[LocalizedValue, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (LocalizedValue(value=raw),)
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be a string or an object")

    values: list[LocalizedValue] = []
    default_value = raw.get("default")
    if default_value is not None:
        values.append(LocalizedValue(value=str(default_value)))
    by_language = raw.get("by_language", {})
    if by_language is not None:
        if not isinstance(by_language, dict):
            raise ValueError(f"{field_name}.by_language must be an object")
        for language_code, value in by_language.items():
            values.append(LocalizedValue(value=str(value), language_code=str(language_code)))
    return tuple(values)


def _parse_commands(raw_commands: Any) -> tuple[CommandSet, ...]:
    if raw_commands is None:
        return ()
    if not isinstance(raw_commands, list):
        raise ValueError("commands must be an array")
    if raw_commands and all(isinstance(item, dict) and "command" in item for item in raw_commands):
        return (
            CommandSet(
                commands=tuple(_parse_command_list(raw_commands, "commands")),
                scope=BotCommandScopeDefault(),
                language_code=None,
            ),
        )

    command_sets: list[CommandSet] = []
    for index, item in enumerate(raw_commands):
        if not isinstance(item, dict):
            raise ValueError(f"commands entry #{index} must be an object")
        commands = tuple(_parse_command_list(item.get("commands"), f"commands[{index}].commands"))
        scope = _parse_scope(item.get("scope"))
        language_code = str(item["language_code"]).strip() if item.get("language_code") else None
        command_sets.append(CommandSet(commands=commands, scope=scope, language_code=language_code))
    return tuple(command_sets)


def _parse_command_list(raw_commands: Any, field_name: str) -> list[BotCommand]:
    if not isinstance(raw_commands, list):
        raise ValueError(f"{field_name} must be an array")
    commands: list[BotCommand] = []
    for index, item in enumerate(raw_commands):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{index}] must be an object")
        command = str(item.get("command", "")).strip().lstrip("/")
        description = str(item.get("description", "")).strip()
        if not command or not description:
            raise ValueError(f"{field_name}[{index}] must contain command and description")
        commands.append(BotCommand(command=command, description=description))
    return commands


def _parse_scope(raw_scope: Any) -> Any:
    if raw_scope is None:
        return BotCommandScopeDefault()
    if not isinstance(raw_scope, dict):
        raise ValueError("scope must be an object")
    scope_type = str(raw_scope.get("type", "default")).strip()
    scope_class = COMMAND_SCOPE_TYPES.get(scope_type)
    if scope_class is None:
        raise ValueError(f"Unsupported scope type: {scope_type}")
    kwargs = {key: value for key, value in raw_scope.items() if key != "type"}
    return scope_class(**kwargs)


def _parse_menu_button(raw_menu_button: Any) -> Any:
    if raw_menu_button is None:
        return MenuButtonCommands()
    if not isinstance(raw_menu_button, dict):
        raise ValueError("menu_button must be an object")

    button_type = str(raw_menu_button.get("type", "commands")).strip()
    if button_type == "commands":
        return MenuButtonCommands()
    if button_type == "default":
        return MenuButtonDefault()
    if button_type == "web_app":
        text = str(raw_menu_button.get("text", "")).strip()
        url = str(raw_menu_button.get("url", "")).strip()
        if not text or not url:
            raise ValueError("menu_button web_app requires text and url")
        return MenuButtonWebApp(text=text, web_app=WebAppInfo(url=url))
    raise ValueError(f"Unsupported menu_button type: {button_type}")


def load_bot_metadata_config(path: str) -> BotMetadataConfig:
    config_path = Path(path)
    LOGGER.info("metadata_loaded", extra={"extra_data": {"path": str(config_path)}})
    raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("bot_metadata.json must contain an object")

    return BotMetadataConfig(
        name=_normalize_localized_values(raw_data.get("name"), "name"),
        description=_normalize_localized_values(raw_data.get("description"), "description"),
        short_description=_normalize_localized_values(raw_data.get("short_description"), "short_description"),
        commands=_parse_commands(raw_data.get("commands")),
        menu_button=_parse_menu_button(raw_data.get("menu_button")),
    )


def _commands_equal(local_commands: tuple[BotCommand, ...], remote_commands: list[BotCommand]) -> bool:
    return [(item.command, item.description) for item in local_commands] == [
        (item.command, item.description) for item in remote_commands
    ]


def _menu_button_equal(local_button: Any, remote_button: Any) -> bool:
    local_type = getattr(local_button, "type", "")
    remote_type = getattr(remote_button, "type", "")
    if local_type != remote_type:
        return False
    if local_type == "web_app":
        local_web_app = getattr(local_button, "web_app", None)
        remote_web_app = getattr(remote_button, "web_app", None)
        return getattr(local_button, "text", "") == getattr(remote_button, "text", "") and getattr(
            local_web_app, "url", ""
        ) == getattr(remote_web_app, "url", "")
    return True


async def _with_retries(operation_name: str, retries: int, coroutine_factory: Any) -> Any:
    attempts = max(retries, 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await coroutine_factory()
        except TelegramAPIError as exc:
            last_error = exc
            LOGGER.warning(
                f"{operation_name}_failed",
                extra={"extra_data": {"attempt": attempt, "retries": attempts, "error": str(exc)}},
            )
            if attempt < attempts:
                await asyncio.sleep(min(attempt, 3))
    if last_error is not None:
        raise last_error


async def _sync_localized_field(
    *,
    field_name: str,
    entries: tuple[LocalizedValue, ...],
    getter: Any,
    setter: Any,
    retries: int,
) -> None:
    for entry in entries:
        language_code = entry.language_code
        try:
            current_value = await _with_retries(
                f"get_{field_name}",
                retries,
                lambda: getter(language_code=language_code),
            )
        except TelegramAPIError:
            continue

        remote_value = getattr(current_value, field_name, "")
        LOGGER.info(
            "current_telegram_value",
            extra={"extra_data": {"field": field_name, "language_code": language_code or "default", "value": remote_value}},
        )
        if remote_value == entry.value:
            LOGGER.info(
                "metadata_already_synced",
                extra={"extra_data": {"field": field_name, "language_code": language_code or "default"}},
            )
            continue

        LOGGER.info(
            "metadata_diff_detected",
            extra={
                "extra_data": {
                    "field": field_name,
                    "language_code": language_code or "default",
                    "current": remote_value,
                    "target": entry.value,
                }
            },
        )
        try:
            await _with_retries(
                f"set_{field_name}",
                retries,
                lambda: setter(language_code=language_code, **{field_name: entry.value}),
            )
            LOGGER.info(
                "metadata_updated",
                extra={"extra_data": {"field": field_name, "language_code": language_code or "default"}},
            )
        except TelegramAPIError:
            continue


async def _sync_commands(bot: Bot, command_sets: tuple[CommandSet, ...], retries: int) -> None:
    for command_set in command_sets:
        scope = command_set.scope
        language_code = command_set.language_code
        scope_type = getattr(scope, "type", "default")
        try:
            current_commands = await _with_retries(
                "get_my_commands",
                retries,
                lambda: bot.get_my_commands(scope=scope, language_code=language_code),
            )
        except TelegramAPIError:
            continue

        LOGGER.info(
            "current_telegram_value",
            extra={
                "extra_data": {
                    "field": "commands",
                    "scope": scope_type,
                    "language_code": language_code or "default",
                    "count": len(current_commands),
                }
            },
        )
        if _commands_equal(command_set.commands, current_commands):
            LOGGER.info(
                "metadata_already_synced",
                extra={"extra_data": {"field": "commands", "scope": scope_type, "language_code": language_code or "default"}},
            )
            continue

        LOGGER.info(
            "metadata_diff_detected",
            extra={
                "extra_data": {
                    "field": "commands",
                    "scope": scope_type,
                    "language_code": language_code or "default",
                    "current_count": len(current_commands),
                    "target_count": len(command_set.commands),
                }
            },
        )
        try:
            await _with_retries(
                "set_my_commands",
                retries,
                lambda: bot.set_my_commands(list(command_set.commands), scope=scope, language_code=language_code),
            )
            LOGGER.info(
                "metadata_updated",
                extra={"extra_data": {"field": "commands", "scope": scope_type, "language_code": language_code or "default"}},
            )
        except TelegramAPIError:
            continue


async def _sync_menu_button(bot: Bot, menu_button: Any, retries: int) -> None:
    try:
        current_menu_button = await _with_retries("get_chat_menu_button", retries, lambda: bot.get_chat_menu_button())
    except TelegramAPIError:
        return

    LOGGER.info(
        "current_telegram_value",
        extra={"extra_data": {"field": "menu_button", "type": getattr(current_menu_button, "type", "")}},
    )
    if _menu_button_equal(menu_button, current_menu_button):
        LOGGER.info("metadata_already_synced", extra={"extra_data": {"field": "menu_button"}})
        return

    LOGGER.info(
        "metadata_diff_detected",
        extra={
            "extra_data": {
                "field": "menu_button",
                "current": getattr(current_menu_button, "type", ""),
                "target": getattr(menu_button, "type", ""),
            }
        },
    )
    try:
        await _with_retries("set_chat_menu_button", retries, lambda: bot.set_chat_menu_button(menu_button=menu_button))
        LOGGER.info("metadata_updated", extra={"extra_data": {"field": "menu_button", "type": getattr(menu_button, "type", "")}})
    except TelegramAPIError:
        return


async def initialize_bot_metadata(bot: Bot, metadata_file_path: str, retries: int = 2) -> None:
    try:
        config = load_bot_metadata_config(metadata_file_path)
    except FileNotFoundError:
        LOGGER.warning("metadata_file_missing", extra={"extra_data": {"path": metadata_file_path}})
        return
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.exception(
            "metadata_file_invalid",
            extra={"extra_data": {"path": metadata_file_path, "error": str(exc)}},
        )
        return

    await _sync_localized_field(
        field_name="name",
        entries=config.name,
        getter=bot.get_my_name,
        setter=bot.set_my_name,
        retries=retries,
    )
    await _sync_localized_field(
        field_name="description",
        entries=config.description,
        getter=bot.get_my_description,
        setter=bot.set_my_description,
        retries=retries,
    )
    await _sync_localized_field(
        field_name="short_description",
        entries=config.short_description,
        getter=bot.get_my_short_description,
        setter=bot.set_my_short_description,
        retries=retries,
    )
    await _sync_commands(bot, config.commands, retries)
    await _sync_menu_button(bot, config.menu_button, retries)
