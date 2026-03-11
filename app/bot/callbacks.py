from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ParcelActionCallback(CallbackData, prefix="parcel"):
    action: str
    parcel_id: int
    page: int = 0


class AdminActionCallback(CallbackData, prefix="admin"):
    action: str
    page: int = 0


class SettingsActionCallback(CallbackData, prefix="settings"):
    action: str
    value: str = ""
