from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ParcelActionCallback(CallbackData, prefix="parcel"):
    action: str
    parcel_id: int
    page: int = 0


class AdminActionCallback(CallbackData, prefix="admin"):
    action: str
    target_id: int = 0
    page: int = 0
    value: str = ""


class SettingsActionCallback(CallbackData, prefix="settings"):
    action: str
    value: str = ""
