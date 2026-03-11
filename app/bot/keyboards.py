from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import AdminActionCallback, ParcelActionCallback, SettingsActionCallback
from app.i18n import normalize_locale, status_label, t


def start_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(locale, "start.add"), callback_data="start:add")],
            [InlineKeyboardButton(text=t(locale, "start.list"), callback_data="start:list")],
            [
                InlineKeyboardButton(text=t(locale, "start.help"), callback_data="start:help"),
                InlineKeyboardButton(text=t(locale, "start.settings"), callback_data="start:settings"),
            ],
        ]
    )


def parcel_actions_keyboard(parcel_id: int, reminders_muted: bool, locale: str, include_back: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t(locale, "btn.refresh"), callback_data=ParcelActionCallback(action="refresh", parcel_id=parcel_id).pack()),
            InlineKeyboardButton(text=t(locale, "btn.details"), callback_data=ParcelActionCallback(action="details", parcel_id=parcel_id).pack()),
        ],
        [InlineKeyboardButton(text=t(locale, "btn.rename"), callback_data=ParcelActionCallback(action="rename", parcel_id=parcel_id).pack())],
        [
            InlineKeyboardButton(text=t(locale, "btn.delete"), callback_data=ParcelActionCallback(action="delete", parcel_id=parcel_id).pack()),
            InlineKeyboardButton(
                text=t(locale, "btn.unmute") if reminders_muted else t(locale, "btn.mute"),
                callback_data=ParcelActionCallback(action="unmute" if reminders_muted else "mute", parcel_id=parcel_id).pack(),
            ),
        ],
    ]
    if include_back:
        rows.append([InlineKeyboardButton(text=t(locale, "btn.back_to_list"), callback_data=ParcelActionCallback(action="list", parcel_id=parcel_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parcel_list_keyboard(parcels: list[dict], page: int, has_next: bool, locale: str) -> InlineKeyboardMarkup:
    rows = []
    for parcel in parcels:
        label = parcel["friendly_name"] or parcel["tracking_number"]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{label} • {status_label(locale, parcel['current_status'])}",
                    callback_data=ParcelActionCallback(action="details", parcel_id=parcel["id"], page=page).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=t(locale, "btn.refresh_all"), callback_data=ParcelActionCallback(action="refresh_all", parcel_id=0, page=page).pack())])
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text=t(locale, "btn.prev"), callback_data=ParcelActionCallback(action="page", parcel_id=0, page=page - 1).pack()))
    if has_next:
        pagination.append(InlineKeyboardButton(text=t(locale, "btn.next"), callback_data=ParcelActionCallback(action="page", parcel_id=0, page=page + 1).pack()))
    if pagination:
        rows.append(pagination)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stale_keyboard(parcel_id: int, locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(locale, "btn.keep_tracking"), callback_data=ParcelActionCallback(action="keep", parcel_id=parcel_id).pack()),
                InlineKeyboardButton(text=t(locale, "btn.delete_parcel"), callback_data=ParcelActionCallback(action="delete", parcel_id=parcel_id).pack()),
            ],
            [InlineKeyboardButton(text=t(locale, "btn.mute"), callback_data=ParcelActionCallback(action="mute", parcel_id=parcel_id).pack())],
        ]
    )


def delivered_keyboard(parcel_id: int, locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(locale, "btn.keep_history"), callback_data=ParcelActionCallback(action="history", parcel_id=parcel_id).pack()),
                InlineKeyboardButton(text=t(locale, "btn.delete"), callback_data=ParcelActionCallback(action="delete", parcel_id=parcel_id).pack()),
            ]
        ]
    )


def admin_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(locale, "admin.stats"), callback_data=AdminActionCallback(action="stats").pack())],
            [InlineKeyboardButton(text=t(locale, "admin.users"), callback_data=AdminActionCallback(action="users").pack())],
            [InlineKeyboardButton(text=t(locale, "admin.parcels"), callback_data=AdminActionCallback(action="parcels").pack())],
        ]
    )


def settings_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(locale, "settings.language"), callback_data="settings:language")],
            [InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="start:home")],
        ]
    )


def language_keyboard(locale: str) -> InlineKeyboardMarkup:
    normalized = normalize_locale(locale)
    english = f"✓ {t(locale, 'language.button_en')}" if normalized == "en" else t(locale, "language.button_en")
    hebrew = f"✓ {t(locale, 'language.button_he')}" if normalized == "he" else t(locale, "language.button_he")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=english, callback_data="settings:set:en")],
            [InlineKeyboardButton(text=hebrew, callback_data="settings:set:he")],
            [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="settings:main")],
        ]
    )
