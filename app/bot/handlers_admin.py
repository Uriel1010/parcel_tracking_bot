from __future__ import annotations

import asyncio
from html import escape

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import AdminActionCallback
from app.bot.keyboards import (
    admin_audit_keyboard,
    admin_confirm_keyboard,
    admin_dashboard_keyboard,
    admin_jobs_keyboard,
    admin_parcel_keyboard,
    admin_parcels_keyboard,
    admin_user_keyboard,
    admin_users_keyboard,
)
from app.config import Settings
from app.db import Database
from app.i18n import status_label, t
from app.services.parcel_service import ParcelService
from app.services.scheduler import SchedulerService
from app.utils.time import utcnow


router = Router()
PAGE_SIZE = 8


class AdminStates(StatesGroup):
    user_search = State()
    parcel_search = State()
    direct_message = State()
    broadcast = State()


def _is_admin(event: Message | CallbackQuery, settings: Settings) -> bool:
    return bool(event.from_user and settings.is_admin(event.from_user.id))


async def _locale(event: Message | CallbackQuery, parcel_service: ParcelService) -> str:
    user = event.from_user
    return await parcel_service.get_user_locale(user.id, user.username, user.first_name, user.language_code)


def _format_stats(stats: dict, locale: str) -> str:
    top_users = "\n".join(f"- {row['telegram_user_id']} @{row['username'] or 'n/a'}: {row['parcel_count']}" for row in stats["top_users"]) or t(locale, "admin.none")
    recent_errors = "\n".join(f"- parcel {row['parcel_id']}: {escape(str(row['last_error_message'] or ''))[:180]}" for row in stats["recent_errors"]) or t(locale, "admin.none")
    return t(locale, "admin.stats_text", users=stats["users"], parcels=stats["parcels"], active=stats["active"], archived=stats["archived"], top_users=top_users, recent_errors=recent_errors)


async def _show_home(target: Message, locale: str, edit: bool = True) -> None:
    text = f"<b>{t(locale, 'admin.dashboard')}</b>\n{t(locale, 'admin.dashboard_hint')}"
    if edit:
        await target.edit_text(text, reply_markup=admin_dashboard_keyboard(locale))
    else:
        await target.answer(text, reply_markup=admin_dashboard_keyboard(locale))


async def _show_users(target: Message, db: Database, locale: str, page: int = 0, search: str = "", edit: bool = True) -> None:
    total = await db.count_users(search)
    users = await db.list_users_page(PAGE_SIZE, page * PAGE_SIZE, search)
    text = f"<b>{t(locale, 'admin.users_title')}</b>\n{t(locale, 'admin.page_info', page=page + 1, total=total)}"
    keyboard = admin_users_keyboard(users, page, total > (page + 1) * PAGE_SIZE, locale)
    if edit: await target.edit_text(text, reply_markup=keyboard)
    else: await target.answer(text, reply_markup=keyboard)


async def _show_user(target: Message, db: Database, locale: str, user_id: int) -> None:
    user = await db.get_admin_user_detail(user_id)
    if not user:
        await target.edit_text(t(locale, "admin.user_missing"), reply_markup=admin_dashboard_keyboard(locale))
        return
    text = t(locale, "admin.user_detail", user_id=user["telegram_user_id"], username=escape(user["username"] or "-"), name=escape(user["first_name"] or "-"), language=user["language_code"], blocked=t(locale, "admin.yes") if user["is_blocked"] else t(locale, "admin.no"), parcels=user["parcel_count"], active=user["active_parcel_count"] or 0)
    await target.edit_text(text, reply_markup=admin_user_keyboard(user, locale))


async def _show_parcels(target: Message, db: Database, locale: str, page: int = 0, status_filter: str = "all", search: str = "", owner_id: int = 0, edit: bool = True) -> None:
    if owner_id:
        total = await db.count_parcels_for_user(owner_id)
        parcels = await db.list_parcels_for_user(owner_id, PAGE_SIZE, page * PAGE_SIZE)
    else:
        total = await db.count_admin_parcels(search, status_filter)
        parcels = await db.list_admin_parcels(PAGE_SIZE, page * PAGE_SIZE, search, status_filter)
    text = f"<b>{t(locale, 'admin.parcels_title')}</b>\n{t(locale, 'admin.page_info', page=page + 1, total=total)}"
    keyboard = admin_parcels_keyboard(parcels, page, total > (page + 1) * PAGE_SIZE, locale, status_filter)
    if edit: await target.edit_text(text, reply_markup=keyboard)
    else: await target.answer(text, reply_markup=keyboard)


async def _show_parcel(target: Message, db: Database, parcel_service: ParcelService, locale: str, parcel_id: int) -> None:
    parcel = await db.get_admin_parcel(parcel_id)
    if not parcel:
        await target.edit_text(t(locale, "parcel.not_found"), reply_markup=admin_dashboard_keyboard(locale))
        return
    text = await parcel_service.build_parcel_details_text(parcel, locale)
    owner = f"\n\n<b>{t(locale, 'admin.owner')}:</b> <code>{parcel['telegram_user_id']}</code> @{escape(parcel['username'] or '-')}"
    await target.edit_text(text + owner, reply_markup=admin_parcel_keyboard(parcel, locale))


@router.message(Command("admin"))
async def handle_admin(message: Message, settings: Settings, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings): return
    await _show_home(message, await _locale(message, parcel_service), edit=False)


@router.message(Command("stats"))
async def handle_stats(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings): return
    locale = await _locale(message, parcel_service)
    await message.answer(_format_stats(await db.get_stats(), locale), reply_markup=admin_dashboard_keyboard(locale))


@router.message(Command("users"))
async def handle_users(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings): return
    await _show_users(message, db, await _locale(message, parcel_service), edit=False)


@router.message(Command("parcels"))
async def handle_parcels(message: Message, settings: Settings, db: Database, parcel_service: ParcelService) -> None:
    if not _is_admin(message, settings): return
    await _show_parcels(message, db, await _locale(message, parcel_service), edit=False)


@router.message(AdminStates.user_search)
async def handle_user_search(message: Message, settings: Settings, db: Database, parcel_service: ParcelService, state: FSMContext) -> None:
    if not _is_admin(message, settings): return
    search = (message.text or "").strip()
    await state.set_state(None)
    await state.update_data(admin_user_search=search)
    await _show_users(message, db, await _locale(message, parcel_service), search=search, edit=False)


@router.message(AdminStates.parcel_search)
async def handle_parcel_search(message: Message, settings: Settings, db: Database, parcel_service: ParcelService, state: FSMContext) -> None:
    if not _is_admin(message, settings): return
    search = (message.text or "").strip()
    await state.set_state(None)
    await state.update_data(admin_parcel_search=search)
    await _show_parcels(message, db, await _locale(message, parcel_service), search=search, edit=False)


@router.message(AdminStates.direct_message)
async def handle_direct_message_input(message: Message, settings: Settings, parcel_service: ParcelService, state: FSMContext) -> None:
    if not _is_admin(message, settings): return
    locale = await _locale(message, parcel_service)
    data = await state.get_data()
    text = message.text or ""
    await state.update_data(content=text)
    await message.answer(f"<b>{t(locale, 'admin.preview')}</b>\n\n{text}", reply_markup=admin_confirm_keyboard("direct_send", int(data["target_id"]), locale))


@router.message(AdminStates.broadcast)
async def handle_broadcast_input(message: Message, settings: Settings, parcel_service: ParcelService, state: FSMContext) -> None:
    if not _is_admin(message, settings): return
    locale = await _locale(message, parcel_service)
    text = message.text or ""
    await state.update_data(content=text)
    await message.answer(f"<b>{t(locale, 'admin.preview')}</b>\n\n{text}", reply_markup=admin_confirm_keyboard("broadcast_send", 0, locale))


@router.callback_query(AdminActionCallback.filter())
async def handle_admin_callbacks(callback: CallbackQuery, callback_data: AdminActionCallback, settings: Settings, db: Database, parcel_service: ParcelService, scheduler_service: SchedulerService, state: FSMContext, bot: Bot) -> None:
    if not _is_admin(callback, settings):
        await callback.answer(t(callback.from_user.language_code, "admin.not_allowed"), show_alert=True)
        return
    locale = await _locale(callback, parcel_service)
    action = callback_data.action
    await callback.answer()

    if action == "home": await state.clear(); await _show_home(callback.message, locale)
    elif action == "overview": await callback.message.edit_text(_format_stats(await db.get_stats(), locale), reply_markup=admin_dashboard_keyboard(locale))
    elif action == "users":
        data = await state.get_data()
        await _show_users(callback.message, db, locale, callback_data.page, data.get("admin_user_search", ""))
    elif action == "user": await _show_user(callback.message, db, locale, callback_data.target_id)
    elif action == "user_search": await state.set_state(AdminStates.user_search); await callback.message.answer(t(locale, "admin.search_user_prompt"))
    elif action == "parcel_search": await state.set_state(AdminStates.parcel_search); await callback.message.answer(t(locale, "admin.search_parcel_prompt"))
    elif action == "parcels":
        data = await state.get_data()
        search = data.get("admin_parcel_search", "") if not callback_data.value else ""
        await _show_parcels(callback.message, db, locale, callback_data.page, callback_data.value or "all", search=search, owner_id=callback_data.target_id)
    elif action == "parcel": await _show_parcel(callback.message, db, parcel_service, locale, callback_data.target_id)
    elif action in {"user_block", "user_unblock"}:
        blocked = action == "user_block"
        await db.set_user_blocked(callback_data.target_id, blocked, callback.from_user.id, utcnow())
        await db.add_audit_log(callback.from_user.id, action, utcnow(), "user", callback_data.target_id)
        await _show_user(callback.message, db, locale, callback_data.target_id)
    elif action == "user_message":
        await state.set_state(AdminStates.direct_message); await state.update_data(target_id=callback_data.target_id)
        await callback.message.answer(t(locale, "admin.message_prompt", user_id=callback_data.target_id))
    elif action == "direct_send":
        data = await state.get_data(); content = data.get("content", "")
        await bot.send_message(callback_data.target_id, content)
        await db.add_audit_log(callback.from_user.id, "direct_message", utcnow(), "user", callback_data.target_id)
        await state.clear(); await callback.message.edit_text(t(locale, "admin.message_sent"), reply_markup=admin_dashboard_keyboard(locale))
    elif action == "user_delete":
        impact = await db.user_delete_impact(callback_data.target_id)
        text = t(locale, "admin.delete_user_confirm", user_id=callback_data.target_id, parcels=impact["parcels"], events=impact["events"])
        await callback.message.edit_text(text, reply_markup=admin_confirm_keyboard("user_delete_confirm", callback_data.target_id, locale))
    elif action == "user_delete_confirm":
        if settings.is_admin(callback_data.target_id):
            await callback.message.edit_text(t(locale, "admin.cannot_delete_admin"), reply_markup=admin_dashboard_keyboard(locale)); return
        impact = await db.user_delete_impact(callback_data.target_id)
        await db.delete_user_data(callback_data.target_id)
        await db.add_audit_log(callback.from_user.id, "user_delete", utcnow(), "user", callback_data.target_id, str(impact))
        await callback.message.edit_text(t(locale, "admin.user_deleted"), reply_markup=admin_dashboard_keyboard(locale))
    elif action.startswith("parcel_"):
        parcel = await db.get_admin_parcel(callback_data.target_id)
        if not parcel: await callback.message.edit_text(t(locale, "parcel.not_found"), reply_markup=admin_dashboard_keyboard(locale)); return
        if action == "parcel_refresh": await parcel_service.refresh_parcel(parcel["id"])
        elif action == "parcel_mute": await db.set_reminders_muted(parcel["id"], True)
        elif action == "parcel_unmute": await db.set_reminders_muted(parcel["id"], False)
        elif action == "parcel_archive": await db.set_archived(parcel["id"], True)
        elif action == "parcel_unarchive": await db.set_archived(parcel["id"], False)
        elif action == "parcel_clear_error": await db.update_notification_state(parcel["id"], clear_error=True)
        elif action == "parcel_delete":
            await callback.message.edit_text(t(locale, "admin.delete_parcel_confirm", tracking=parcel["tracking_number"]), reply_markup=admin_confirm_keyboard("parcel_delete_confirm", parcel["id"], locale)); return
        elif action == "parcel_delete_confirm": await db.delete_parcel(parcel["id"]); await callback.message.edit_text(t(locale, "parcel.deleted", tracking_number=parcel["tracking_number"]), reply_markup=admin_dashboard_keyboard(locale)); return
        await db.add_audit_log(callback.from_user.id, action, utcnow(), "parcel", parcel["id"])
        await _show_parcel(callback.message, db, parcel_service, locale, parcel["id"])
    elif action == "jobs":
        jobs = await db.list_job_runs(); lines = [f"- {escape(row['job_name'])}: {row['last_status'] or '-'} | {row['last_run_at'] or '-'}\n  {escape(row['last_error'] or '')}" for row in jobs]
        await callback.message.edit_text(f"<b>{t(locale, 'admin.jobs')}</b>\n" + ("\n".join(lines) or t(locale, "admin.none")), reply_markup=admin_jobs_keyboard(locale))
    elif action == "job_confirm":
        await callback.message.edit_text(t(locale, "admin.run_job_confirm", job=callback_data.value), reply_markup=admin_confirm_keyboard("job_run", 0, locale, callback_data.value))
    elif action == "job_run":
        if callback_data.value == "refresh": await scheduler_service.refresh_active_parcels()
        else: await scheduler_service.send_stale_reminders()
        await db.add_audit_log(callback.from_user.id, "job_run", utcnow(), "job", callback_data.value)
        await callback.message.edit_text(t(locale, "admin.job_finished"), reply_markup=admin_dashboard_keyboard(locale))
    elif action == "broadcast":
        await state.set_state(AdminStates.broadcast); await callback.message.answer(t(locale, "admin.broadcast_prompt"))
    elif action == "broadcast_send":
        data = await state.get_data(); content = data.get("content", ""); recipients = await db.list_broadcast_recipients()
        run_id = await db.create_broadcast_run(callback.from_user.id, content, len(recipients), utcnow()); success = failure = 0
        for recipient in recipients:
            try: await bot.send_message(recipient, content); success += 1
            except Exception: failure += 1
            await asyncio.sleep(0.04)
        await db.finish_broadcast_run(run_id, success, failure, utcnow())
        await db.add_audit_log(callback.from_user.id, "broadcast", utcnow(), "broadcast", run_id, f"success={success},failure={failure}")
        await state.clear(); await callback.message.edit_text(t(locale, "admin.broadcast_done", success=success, failure=failure), reply_markup=admin_dashboard_keyboard(locale))
    elif action == "audit":
        total = await db.count_audit_log()
        rows = await db.list_audit_log(PAGE_SIZE, callback_data.page * PAGE_SIZE)
        lines = [f"- {row['created_at']} | {escape(row['action'])} | {escape(row['target_type'] or '-')}: {escape(row['target_id'] or '-')}" for row in rows]
        text = f"<b>{t(locale, 'admin.audit')}</b>\n{t(locale, 'admin.page_info', page=callback_data.page + 1, total=total)}\n" + ("\n".join(lines) or t(locale, "admin.none"))
        await callback.message.edit_text(text, reply_markup=admin_audit_keyboard(callback_data.page, total > (callback_data.page + 1) * PAGE_SIZE, locale))
