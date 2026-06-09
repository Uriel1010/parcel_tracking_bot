from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.db import Database


class AccessMiddleware(BaseMiddleware):
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user and not self.settings.is_admin(user.id) and await self.db.is_user_blocked(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Access disabled.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Access disabled.")
            return None
        return await handler(event, data)
