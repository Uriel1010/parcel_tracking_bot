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


def parcel_actions_keyboard(
    parcel_id: int,
    reminders_muted: bool,
    locale: str,
    include_back: bool = False,
    include_hfd_phone_edit: bool = False,
) -> InlineKeyboardMarkup:
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
    if include_hfd_phone_edit:
        rows.append([InlineKeyboardButton(text=t(locale, "btn.edit_hfd_phone"), callback_data=ParcelActionCallback(action="edit_hfd_phone", parcel_id=parcel_id).pack())])
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


def delivered_keyboard(parcel_id: int, locale: str, include_hfd_phone_edit: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t(locale, "btn.keep_history"), callback_data=ParcelActionCallback(action="history", parcel_id=parcel_id).pack()),
            InlineKeyboardButton(text=t(locale, "btn.delete"), callback_data=ParcelActionCallback(action="delete", parcel_id=parcel_id).pack()),
        ]
    ]
    if include_hfd_phone_edit:
        rows.append([InlineKeyboardButton(text=t(locale, "btn.edit_hfd_phone"), callback_data=ParcelActionCallback(action="edit_hfd_phone", parcel_id=parcel_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def admin_dashboard_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "admin.stats"), callback_data=AdminActionCallback(action="overview").pack())],
        [InlineKeyboardButton(text=t(locale, "admin.users"), callback_data=AdminActionCallback(action="users").pack()), InlineKeyboardButton(text=t(locale, "admin.parcels"), callback_data=AdminActionCallback(action="parcels").pack())],
        [InlineKeyboardButton(text=t(locale, "admin.errors"), callback_data=AdminActionCallback(action="parcels", value="errors").pack()), InlineKeyboardButton(text=t(locale, "admin.jobs"), callback_data=AdminActionCallback(action="jobs").pack())],
        [InlineKeyboardButton(text=t(locale, "admin.broadcast"), callback_data=AdminActionCallback(action="broadcast").pack()), InlineKeyboardButton(text=t(locale, "admin.audit"), callback_data=AdminActionCallback(action="audit").pack())],
    ])


def admin_users_keyboard(users: list[dict], page: int, has_next: bool, locale: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{'BLOCKED ' if row['is_blocked'] else ''}{row['telegram_user_id']} @{row['username'] or '-'}", callback_data=AdminActionCallback(action="user", target_id=row["telegram_user_id"], page=page).pack())] for row in users]
    rows.append([InlineKeyboardButton(text=t(locale, "admin.search"), callback_data=AdminActionCallback(action="user_search").pack())])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text=t(locale, "btn.prev"), callback_data=AdminActionCallback(action="users", page=page - 1).pack()))
    if has_next: nav.append(InlineKeyboardButton(text=t(locale, "btn.next"), callback_data=AdminActionCallback(action="users", page=page + 1).pack()))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_keyboard(user: dict, locale: str) -> InlineKeyboardMarkup:
    target = int(user["telegram_user_id"])
    block_action = "user_unblock" if user["is_blocked"] else "user_block"
    block_label = t(locale, "admin.unblock") if user["is_blocked"] else t(locale, "admin.block")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "admin.message"), callback_data=AdminActionCallback(action="user_message", target_id=target).pack()), InlineKeyboardButton(text=t(locale, "admin.user_parcels"), callback_data=AdminActionCallback(action="parcels", target_id=target).pack())],
        [InlineKeyboardButton(text=block_label, callback_data=AdminActionCallback(action=block_action, target_id=target).pack())],
        [InlineKeyboardButton(text=t(locale, "admin.delete_user"), callback_data=AdminActionCallback(action="user_delete", target_id=target).pack())],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="users").pack())],
    ])


def admin_parcels_keyboard(parcels: list[dict], page: int, has_next: bool, locale: str, value: str = "all") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{row['tracking_number']} | {row['current_status']}", callback_data=AdminActionCallback(action="parcel", target_id=row["id"], page=page, value=value).pack())] for row in parcels]
    rows.append([InlineKeyboardButton(text=t(locale, "admin.search"), callback_data=AdminActionCallback(action="parcel_search").pack())])
    rows.append([
        InlineKeyboardButton(text=t(locale, "admin.active"), callback_data=AdminActionCallback(action="parcels", value="active").pack()),
        InlineKeyboardButton(text=t(locale, "admin.errors"), callback_data=AdminActionCallback(action="parcels", value="errors").pack()),
        InlineKeyboardButton(text=t(locale, "admin.archived"), callback_data=AdminActionCallback(action="parcels", value="archived").pack()),
    ])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text=t(locale, "btn.prev"), callback_data=AdminActionCallback(action="parcels", page=page - 1, value=value).pack()))
    if has_next: nav.append(InlineKeyboardButton(text=t(locale, "btn.next"), callback_data=AdminActionCallback(action="parcels", page=page + 1, value=value).pack()))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_parcel_keyboard(parcel: dict, locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "btn.refresh"), callback_data=AdminActionCallback(action="parcel_refresh", target_id=parcel["id"]).pack()), InlineKeyboardButton(text=t(locale, "btn.unmute") if parcel["reminders_muted"] else t(locale, "btn.mute"), callback_data=AdminActionCallback(action="parcel_unmute" if parcel["reminders_muted"] else "parcel_mute", target_id=parcel["id"]).pack())],
        [InlineKeyboardButton(text=t(locale, "admin.unarchive") if parcel["archived"] else t(locale, "admin.archive"), callback_data=AdminActionCallback(action="parcel_unarchive" if parcel["archived"] else "parcel_archive", target_id=parcel["id"]).pack()), InlineKeyboardButton(text=t(locale, "admin.clear_error"), callback_data=AdminActionCallback(action="parcel_clear_error", target_id=parcel["id"]).pack())],
        [InlineKeyboardButton(text=t(locale, "btn.delete"), callback_data=AdminActionCallback(action="parcel_delete", target_id=parcel["id"]).pack())],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="parcels").pack())],
    ])


def admin_jobs_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "admin.run_refresh"), callback_data=AdminActionCallback(action="job_confirm", value="refresh").pack())],
        [InlineKeyboardButton(text=t(locale, "admin.run_stale"), callback_data=AdminActionCallback(action="job_confirm", value="stale").pack())],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="home").pack())],
    ])


def admin_confirm_keyboard(action: str, target_id: int, locale: str, value: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "admin.confirm"), callback_data=AdminActionCallback(action=action, target_id=target_id, value=value).pack())],
        [InlineKeyboardButton(text=t(locale, "admin.cancel"), callback_data=AdminActionCallback(action="home").pack())],
    ])


def admin_audit_keyboard(page: int, has_next: bool, locale: str) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=t(locale, "btn.prev"), callback_data=AdminActionCallback(action="audit", page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text=t(locale, "btn.next"), callback_data=AdminActionCallback(action="audit", page=page + 1).pack()))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=AdminActionCallback(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
