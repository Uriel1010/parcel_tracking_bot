from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import SettingsActionCallback
from app.bot.handlers_parcels import send_parcel_list
from app.bot.keyboards import language_keyboard, parcel_actions_keyboard, settings_keyboard, start_keyboard
from app.i18n import normalize_locale, t
from app.services.parcel_service import ParcelService


router = Router()


class AddParcelStates(StatesGroup):
    waiting_for_tracking_number = State()
    waiting_for_friendly_name = State()


async def _user_locale(message_or_callback: Message | CallbackQuery, parcel_service: ParcelService) -> str:
    user = message_or_callback.from_user
    return await parcel_service.get_user_locale(user.id, user.username, user.first_name, user.language_code)


async def _render_home_text(locale: str) -> str:
    return f"{t(locale, 'start.title')}\n{t(locale, 'start.subtitle')}"


def _parse_language_argument(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if value in {"he", "heb", "hebrew", "עברית"}:
        return "he"
    if value in {"en", "eng", "english", "אנגלית"}:
        return "en"
    return None


async def _render_settings_text(locale: str) -> str:
    return f"{t(locale, 'settings.title')}\n{t(locale, 'settings.hint')}"


async def _render_language_text(locale: str) -> str:
    current_label = t(locale, "language.hebrew") if normalize_locale(locale) == "he" else t(locale, "language.english")
    return (
        f"{t(locale, 'settings.language_title')}\n"
        f"{t(locale, 'settings.language_current', language=current_label)}\n"
        f"{t(locale, 'language.usage')}"
    )


async def _show_settings_screen(message: Message, locale: str) -> None:
    await message.answer(await _render_settings_text(locale), reply_markup=settings_keyboard(locale))


@router.message(CommandStart())
async def handle_start(message: Message, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    await message.answer(await _render_home_text(locale), reply_markup=start_keyboard(locale))


@router.message(Command("help"))
async def handle_help(message: Message, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    await message.answer(t(locale, "help.long"))


@router.message(Command("settings"))
async def handle_settings_command(message: Message, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    await _show_settings_screen(message, locale)


@router.message(Command("language"))
async def handle_language_command(message: Message, command: CommandObject, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    requested_locale = _parse_language_argument(command.args)
    if command.args and requested_locale is None:
        await message.answer(t(locale, "language.invalid"), reply_markup=language_keyboard(locale))
        return
    if requested_locale is None:
        await message.answer(await _render_language_text(locale), reply_markup=language_keyboard(locale))
        return

    await parcel_service.db.set_user_language(message.from_user.id, requested_locale)
    current_label = t(requested_locale, "language.hebrew") if requested_locale == "he" else t(requested_locale, "language.english")
    await message.answer(
        t(requested_locale, "language.changed", language=current_label),
        reply_markup=language_keyboard(requested_locale),
    )


@router.callback_query(F.data == "start:add")
async def handle_start_add(callback: CallbackQuery, state: FSMContext, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await state.set_state(AddParcelStates.waiting_for_tracking_number)
    await callback.message.edit_text(t(locale, "prompt.tracking"))
    await callback.answer()


@router.callback_query(F.data == "start:list")
async def handle_start_list(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await send_parcel_list(callback.message, parcel_service, callback.from_user.id, 0, parcel_service.settings.page_size, locale, edit=True)
    await callback.answer()


@router.callback_query(F.data == "start:help")
async def handle_start_help(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await callback.message.edit_text(t(locale, "help.short"), reply_markup=settings_keyboard(locale))
    await callback.answer()


@router.callback_query(F.data == "start:settings")
async def handle_start_settings(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await callback.message.edit_text(await _render_settings_text(locale), reply_markup=settings_keyboard(locale))
    await callback.answer()


@router.callback_query(F.data == "settings:main")
async def handle_settings_main(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await callback.message.edit_text(await _render_settings_text(locale), reply_markup=settings_keyboard(locale))
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def handle_settings_language(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await callback.message.edit_text(await _render_language_text(locale), reply_markup=language_keyboard(locale))
    await callback.answer()


@router.callback_query(F.data.in_({"settings:set:en", "settings:set:he"}))
async def handle_settings_set_language(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    new_locale = "he" if callback.data.endswith(":he") else "en"
    await parcel_service.db.set_user_language(callback.from_user.id, new_locale)
    await callback.message.edit_text(t(new_locale, "settings.saved"), reply_markup=settings_keyboard(new_locale))
    await callback.answer()


@router.callback_query(F.data == "start:home")
async def handle_start_home(callback: CallbackQuery, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    await callback.message.edit_text(await _render_home_text(locale), reply_markup=start_keyboard(locale))
    await callback.answer()


@router.callback_query(SettingsActionCallback.filter())
async def handle_settings_callbacks(callback: CallbackQuery, callback_data: SettingsActionCallback, parcel_service: ParcelService) -> None:
    locale = await _user_locale(callback, parcel_service)
    if callback_data.action == "main":
        await callback.message.edit_text(await _render_settings_text(locale), reply_markup=settings_keyboard(locale))
    elif callback_data.action == "language":
        await callback.message.edit_text(await _render_language_text(locale), reply_markup=language_keyboard(locale))
    elif callback_data.action == "set_language":
        new_locale = normalize_locale(callback_data.value)
        await parcel_service.db.set_user_language(callback.from_user.id, new_locale)
        await callback.message.edit_text(t(new_locale, "settings.saved"), reply_markup=settings_keyboard(new_locale))
    await callback.answer()


@router.message(Command("add"))
async def handle_add_command(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    await state.set_state(AddParcelStates.waiting_for_tracking_number)
    await message.answer(t(locale, "prompt.tracking"))


@router.message(AddParcelStates.waiting_for_tracking_number)
async def handle_tracking_input(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    raw_tracking_number = message.text or ""
    if not raw_tracking_number:
        await message.answer(t(locale, "prompt.tracking"))
        return
    await state.update_data(raw_tracking_number=raw_tracking_number)
    await state.set_state(AddParcelStates.waiting_for_friendly_name)
    await message.answer(t(locale, "prompt.friendly_name"))


@router.message(Command("skip"), AddParcelStates.waiting_for_friendly_name)
async def handle_skip_friendly_name(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    await _finish_add_parcel(message, state, parcel_service, None)


@router.message(AddParcelStates.waiting_for_friendly_name)
async def handle_friendly_name_input(message: Message, state: FSMContext, parcel_service: ParcelService) -> None:
    await _finish_add_parcel(message, state, parcel_service, message.text or "")


async def _finish_add_parcel(message: Message, state: FSMContext, parcel_service: ParcelService, friendly_name: str | None) -> None:
    locale = await _user_locale(message, parcel_service)
    data = await state.get_data()
    raw_tracking_number = data.get("raw_tracking_number", "")
    parcel, info = await parcel_service.add_parcel_for_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        raw_tracking_number,
        friendly_name=friendly_name,
        locale=locale,
    )
    await state.clear()
    if parcel is None:
        await message.answer(info)
        return
    summary = await parcel_service.build_parcel_summary_text(parcel, locale)
    await message.answer(
        f"{info}\n\n{summary}",
        parse_mode="HTML",
        reply_markup=parcel_actions_keyboard(parcel["id"], bool(parcel["reminders_muted"]), locale),
    )


@router.message(F.text.regexp(r"^[A-Za-z0-9\- ]{8,40}$"))
async def handle_freeform_tracking(message: Message, parcel_service: ParcelService) -> None:
    locale = await _user_locale(message, parcel_service)
    parcel, info = await parcel_service.add_parcel_for_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.text or "",
        locale=locale,
    )
    if parcel is None:
        return
    summary = await parcel_service.build_parcel_summary_text(parcel, locale)
    await message.answer(
        f"{info}\n\n{summary}",
        parse_mode="HTML",
        reply_markup=parcel_actions_keyboard(parcel["id"], bool(parcel["reminders_muted"]), locale),
    )
