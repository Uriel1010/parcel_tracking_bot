from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import ParcelActionCallback
from app.bot.keyboards import delivered_keyboard, parcel_actions_keyboard, parcel_list_keyboard
from app.i18n import t
from app.services.parcel_service import ParcelService
from app.services.parser_utils import is_hfd_tracking_number


router = Router()


class RenameParcelStates(StatesGroup):
    waiting_for_name = State()


class HfdPhoneStates(StatesGroup):
    waiting_for_phone = State()


async def _user_locale(message_or_callback: Message | CallbackQuery, parcel_service: ParcelService) -> str:
    user = message_or_callback.from_user
    return await parcel_service.get_user_locale(user.id, user.username, user.first_name, user.language_code)


async def send_parcel_list(
    message: Message,
    parcel_service: ParcelService,
    user_id: int,
    page: int,
    page_size: int,
    locale: str,
    edit: bool = False,
) -> None:
    offset = page * page_size
    parcels = await parcel_service.db.list_parcels_for_user(user_id, page_size, offset)
    total = await parcel_service.db.count_parcels_for_user(user_id)
    if not parcels:
        if edit:
            await message.edit_text(t(locale, "parcel.none"))
        else:
            await message.answer(t(locale, "parcel.none"))
        return
    body = "\n\n".join([await parcel_service.build_parcel_summary_text(parcel, locale) for parcel in parcels])
    text = f"<b>{t(locale, 'parcel.list_title')}</b>\n\n{body}"
    has_next = total > offset + len(parcels)
    keyboard = parcel_list_keyboard(parcels, page, has_next, locale)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("myparcels"))
async def handle_myparcels(message: Message, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    await send_parcel_list(message, parcel_service, message.from_user.id, 0, parcel_service.settings.page_size, locale)


@router.callback_query(ParcelActionCallback.filter())
async def handle_parcel_actions(
    callback: CallbackQuery,
    callback_data: ParcelActionCallback,
    parcel_service: ParcelService,
    state: FSMContext,
) -> None:
    locale = await _user_locale(callback, parcel_service)
    if callback_data.action in {"refresh_all", "page"}:
        await callback.answer()
        if callback_data.action == "refresh_all":
            refreshed = await parcel_service.refresh_all_user_parcels(callback.from_user.id)
            await callback.message.answer(t(locale, "parcel.refreshed_count", count=refreshed))
        await send_parcel_list(
            callback.message,
            parcel_service,
            callback.from_user.id,
            callback_data.page,
            parcel_service.settings.page_size,
            locale,
            edit=True,
        )
        return

    parcel = await parcel_service.db.get_parcel_for_user(callback_data.parcel_id, callback.from_user.id)
    if parcel is None:
        await callback.answer(t(locale, "parcel.not_found"), show_alert=True)
        return

    await callback.answer()

    if callback_data.action == "details":
        text = await parcel_service.build_parcel_details_text(parcel, locale)
        keyboard = (
            delivered_keyboard(parcel["id"], locale, include_hfd_phone_edit=is_hfd_tracking_number(parcel["tracking_number"]))
            if parcel["current_status"] == "delivered"
            else parcel_actions_keyboard(
                parcel["id"],
                bool(parcel["reminders_muted"]),
                locale,
                include_back=True,
                include_hfd_phone_edit=is_hfd_tracking_number(parcel["tracking_number"]),
            )
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    elif callback_data.action == "refresh":
        refreshed = await parcel_service.refresh_parcel(parcel["id"])
        text = await parcel_service.build_parcel_details_text(refreshed, locale)
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=parcel_actions_keyboard(
                refreshed["id"],
                bool(refreshed["reminders_muted"]),
                locale,
                include_back=True,
                include_hfd_phone_edit=is_hfd_tracking_number(refreshed["tracking_number"]),
            ),
        )
    elif callback_data.action == "delete":
        await parcel_service.db.delete_parcel(parcel["id"])
        await callback.message.edit_text(t(locale, "parcel.deleted", tracking_number=parcel["tracking_number"]))
    elif callback_data.action == "mute":
        await parcel_service.db.set_reminders_muted(parcel["id"], True)
        updated = await parcel_service.db.get_parcel_for_user(parcel["id"], callback.from_user.id)
        await callback.message.edit_text(
            await parcel_service.build_parcel_details_text(updated, locale),
            parse_mode="HTML",
            reply_markup=parcel_actions_keyboard(
                updated["id"],
                True,
                locale,
                include_back=True,
                include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"]),
            ),
        )
    elif callback_data.action == "unmute":
        await parcel_service.db.set_reminders_muted(parcel["id"], False)
        updated = await parcel_service.db.get_parcel_for_user(parcel["id"], callback.from_user.id)
        await callback.message.edit_text(
            await parcel_service.build_parcel_details_text(updated, locale),
            parse_mode="HTML",
            reply_markup=parcel_actions_keyboard(
                updated["id"],
                False,
                locale,
                include_back=True,
                include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"]),
            ),
        )
    elif callback_data.action == "keep":
        await parcel_service.maybe_mark_keep_tracking(parcel["id"])
        updated = await parcel_service.db.get_parcel_for_user(parcel["id"], callback.from_user.id)
        await callback.message.edit_text(
            await parcel_service.build_parcel_details_text(updated, locale),
            parse_mode="HTML",
            reply_markup=parcel_actions_keyboard(
                updated["id"],
                bool(updated["reminders_muted"]),
                locale,
                include_back=True,
                include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"]),
            ),
        )
    elif callback_data.action == "history":
        await parcel_service.keep_for_history(parcel["id"])
        updated = await parcel_service.db.get_parcel_for_user(parcel["id"], callback.from_user.id)
        await callback.message.edit_text(
            await parcel_service.build_parcel_details_text(updated, locale),
            parse_mode="HTML",
            reply_markup=delivered_keyboard(updated["id"], locale, include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"])),
        )
    elif callback_data.action == "list":
        await send_parcel_list(callback.message, parcel_service, callback.from_user.id, callback_data.page, parcel_service.settings.page_size, locale, edit=True)
    elif callback_data.action == "rename":
        await state.set_state(RenameParcelStates.waiting_for_name)
        await state.update_data(rename_parcel_id=parcel["id"])
        await callback.message.answer(t(locale, "prompt.rename"))
    elif callback_data.action == "edit_hfd_phone":
        await state.set_state(HfdPhoneStates.waiting_for_phone)
        await state.update_data(hfd_phone_parcel_id=parcel["id"])
        await callback.message.answer(t(locale, "prompt.hfd_phone_edit"))


@router.message(Command("clearname"), RenameParcelStates.waiting_for_name)
async def handle_clear_name(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    await _finish_rename(message, state, parcel_service, None)


@router.message(RenameParcelStates.waiting_for_name)
async def handle_name_input(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    await _finish_rename(message, state, parcel_service, message.text or "")


async def _finish_rename(message: Message, state: FSMContext, parcel_service: ParcelService, friendly_name: str | None) -> None:
    locale = await _user_locale(message, parcel_service)
    data = await state.get_data()
    parcel_id = data.get("rename_parcel_id")
    if not parcel_id:
        await state.clear()
        await message.answer(t(locale, "parcel.rename_expired"))
        return
    parcel = await parcel_service.db.get_parcel_for_user(int(parcel_id), message.from_user.id)
    if parcel is None:
        await state.clear()
        await message.answer(t(locale, "parcel.not_found"))
        return
    updated = await parcel_service.rename_parcel(parcel["id"], friendly_name)
    await state.clear()
    text = await parcel_service.build_parcel_details_text(updated, locale)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=parcel_actions_keyboard(
            updated["id"],
            bool(updated["reminders_muted"]),
            locale,
            include_back=True,
            include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"]),
        ),
    )


@router.message(HfdPhoneStates.waiting_for_phone)
async def handle_hfd_phone_edit(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    data = await state.get_data()
    parcel_id = data.get("hfd_phone_parcel_id")
    if not parcel_id:
        await state.clear()
        await message.answer(t(locale, "parcel.edit_hfd_phone_expired"))
        return
    parcel = await parcel_service.db.get_parcel_for_user(int(parcel_id), message.from_user.id)
    if parcel is None:
        await state.clear()
        await message.answer(t(locale, "parcel.not_found"))
        return
    normalized = parcel_service.normalize_hfd_phone_number(message.text or "")
    if normalized is None:
        await message.answer(t(locale, "prompt.invalid_hfd_phone"))
        return
    updated = await parcel_service.set_hfd_phone_number(parcel["id"], normalized)
    await state.clear()
    text = f"{t(locale, 'parcel.hfd_phone_updated')}\n\n{await parcel_service.build_parcel_details_text(updated, locale)}"
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=parcel_actions_keyboard(
            updated["id"],
            bool(updated["reminders_muted"]),
            locale,
            include_back=True,
            include_hfd_phone_edit=is_hfd_tracking_number(updated["tracking_number"]),
        ),
    )
