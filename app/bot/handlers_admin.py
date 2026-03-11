from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import AdminActionCallback
from app.bot.keyboards import admin_keyboard
from app.config import Settings
from app.db import Database
from app.i18n import t
from app.services.parcel_service import ParcelService


router = Router()


def _is_admin(message_or_callback: Message | CallbackQuery, settings: Settings) -> bool:
    return message_or_callback.from_user.id == settings.admin_chat_id


def _format_stats(stats: dict, locale: str) -> str:
    top_users = "\n".join(
        f"- {row['telegram_user_id']} @{row['username'] or 'n/a'}: {row['parcel_count']}"
        for row in stats["top_users"]
    ) or t(locale, "admin.none")
    recent_errors = "\n".join(
        f"- parcel {row['parcel_id']}: {row['last_error_message']}"
        for row in stats["recent_errors"]
    ) or t(locale, "admin.none")
    return t(
        locale,
        "admin.stats_text",
        users=stats["users"],
        parcels=stats["parcels"],
        active=stats["active"],
        archived=stats["archived"],
        top_users=top_users,
        recent_errors=recent_errors,
    )


async def _locale(message_or_callback: Message | CallbackQuery, parcel_service: ParcelService) -> str:
    user = message_or_callback.from_user
    return await parcel_service.get_user_locale(user.id, user.username, user.first_name, user.language_code)


@router.message(Command("admin"))
async def handle_admin(message: Message, settings: Settings, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings):
        return
    locale = await _locale(message, parcel_service)
    await message.answer(t(locale, "admin.dashboard"), reply_markup=admin_keyboard(locale))


@router.message(Command("stats"))
async def handle_stats(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings):
        return
    locale = await _locale(message, parcel_service)
    await message.answer(_format_stats(await db.get_stats(), locale))


@router.message(Command("users"))
async def handle_users(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings):
        return
    locale = await _locale(message, parcel_service)
    users = await db.list_users()
    lines = [f"- {row['telegram_user_id']} @{row['username'] or 'n/a'} ({row['parcel_count']}, {row['language_code']})" for row in users]
    await message.answer(t(locale, "admin.users_title") + "\n" + ("\n".join(lines) if lines else t(locale, "admin.none")))


@router.message(Command("parcels"))
async def handle_parcels(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings):
        return
    locale = await _locale(message, parcel_service)
    parcels = await db.list_recent_parcels()
    lines = [f"- {row['tracking_number']} | {row['current_status']} | owner {row['telegram_user_id']}" for row in parcels]
    await message.answer(t(locale, "admin.parcels_title") + "\n" + ("\n".join(lines) if lines else t(locale, "admin.none")))


@router.callback_query(AdminActionCallback.filter())
async def handle_admin_callbacks(callback: CallbackQuery, callback_data: AdminActionCallback, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(callback, settings):
        await callback.answer(t(callback.from_user.language_code, "admin.not_allowed"), show_alert=True)
        return
    locale = await _locale(callback, parcel_service)
    if callback_data.action == "stats":
        await callback.message.edit_text(_format_stats(await db.get_stats(), locale), reply_markup=admin_keyboard(locale))
    elif callback_data.action == "users":
        users = await db.list_users()
        lines = [f"- {row['telegram_user_id']} @{row['username'] or 'n/a'} ({row['parcel_count']}, {row['language_code']})" for row in users]
        await callback.message.edit_text(t(locale, "admin.users_title") + "\n" + ("\n".join(lines) if lines else t(locale, "admin.none")), reply_markup=admin_keyboard(locale))
    elif callback_data.action == "parcels":
        parcels = await db.list_recent_parcels()
        lines = [f"- {row['tracking_number']} | {row['current_status']} | owner {row['telegram_user_id']}" for row in parcels]
        await callback.message.edit_text(t(locale, "admin.parcels_title") + "\n" + ("\n".join(lines) if lines else t(locale, "admin.none")), reply_markup=admin_keyboard(locale))
    await callback.answer()
