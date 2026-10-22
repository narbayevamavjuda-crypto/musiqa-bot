import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

import db
import texts
from config import ADMINS

log = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]

# Xotiradagi tezkor ro'yxatlar (bazaga har safar murojaat qilmaslik uchun)
seen_users: set[int] = set()
banned_users: set[int] = set()
_sub_ok_until: dict[int, float] = {}  # obunasi tasdiqlangan foydalanuvchi -> muddat
SUB_CACHE_SECONDS = 300


def reset_sub_cache():
    _sub_ok_until.clear()


# ---------------- Flooddan himoya ----------------
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float):
        self.rate = rate
        self.last: dict[int, float] = {}

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user and user.id not in ADMINS:
            now = time.monotonic()
            if now - self.last.get(user.id, 0) < self.rate:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ Biroz sekinroq...")
                return None
            self.last[user.id] = now
            if len(self.last) > 50_000:
                self.last.clear()
        return await handler(event, data)


# ---------------- Ro'yxatga olish va ban ----------------
class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        if user.id in banned_users:
            if isinstance(event, CallbackQuery):
                await event.answer(texts.BANNED, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(texts.BANNED)
            return None
        if user.id not in seen_users:
            await db.add_user(user.id, user.full_name, user.username)
            seen_users.add(user.id)
        return await handler(event, data)


# ---------------- Majburiy obuna ----------------
async def unsubscribed_channels(bot: Bot, user_id: int) -> list[dict]:
    missing = []
    for ch in await db.get_channels():
        try:
            member = await bot.get_chat_member(ch["chat_id"], user_id)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            # Bot kanaldan chiqarilgan yoki admin emas — foydalanuvchini to'smaymiz
            log.warning("Kanal %s tekshirilmadi: %s", ch["chat_id"], e)
            continue
        left = member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) or (
            member.status == ChatMemberStatus.RESTRICTED and not getattr(member, "is_member", True)
        )
        # Yopiq kanalga "qo'shilish so'rovi" yuborgan bo'lsa ham obuna hisoblanadi
        if left and not await db.has_join_request(ch["chat_id"], user_id):
            missing.append(ch)
    return missing


def subscribe_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"➕ {ch['title']}", url=ch["link"])] for ch in channels]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def is_subscribed(bot: Bot, user_id: int) -> list[dict]:
    """Obuna bo'linmagan kanallar ro'yxatini qaytaradi (bo'sh bo'lsa — hammasi joyida)."""
    if _sub_ok_until.get(user_id, 0) > time.monotonic():
        return []
    missing = await unsubscribed_channels(bot, user_id)
    if not missing:
        _sub_ok_until[user_id] = time.monotonic() + SUB_CACHE_SECONDS
    return missing


FREE_COMMANDS = ("/privacy", "/terms", "/help", "/delete_me")


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id in ADMINS:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
        if isinstance(event, Message) and event.text and event.text.split()[0] in FREE_COMMANDS:
            return await handler(event, data)

        missing = await is_subscribed(data["bot"], user.id)
        if not missing:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(texts.SUBSCRIBE, reply_markup=subscribe_kb(missing))
        elif isinstance(event, CallbackQuery):
            await event.answer("Avval kanallarga obuna bo'ling!", show_alert=True)
            await event.message.answer(texts.SUBSCRIBE, reply_markup=subscribe_kb(missing))
        return None
