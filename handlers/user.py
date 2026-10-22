import asyncio
import html
import logging
import os
import secrets
from collections import OrderedDict

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    CallbackQuery,
    ChatJoinRequest,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import db
import music
import texts
from config import MAX_FILE_SIZE
from middlewares import is_subscribed, seen_users, subscribe_kb

log = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 10
download_limit = asyncio.Semaphore(2)  # bir vaqtda nechta yuklash (bepul server uchun)
_in_progress: set[str] = set()

# Qidiruv natijalari xotirada saqlanadi (token -> natijalar)
_results: "OrderedDict[str, dict]" = OrderedDict()


def _store(query: str, items: list[dict]) -> str:
    token = secrets.token_hex(4)
    _results[token] = {"q": query, "items": items}
    while len(_results) > 3000:
        _results.popitem(last=False)
    return token


def _page(token: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    data = _results[token]
    items = data["items"]
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE

    lines = [f"🔎 <b>{html.escape(data['q'])}</b>  ·  {page + 1}/{pages}\n"]
    for i, it in enumerate(chunk, start + 1):
        lines.append(f"<b>{i}.</b> {html.escape(it['title'])} <i>({music.fmt_duration(it['duration'])})</i>")

    buttons = [
        InlineKeyboardButton(text=str(i), callback_data=f"dl:{token}:{i - 1}")
        for i in range(start + 1, start + len(chunk) + 1)
    ]
    rows = [buttons[i : i + 5] for i in range(0, len(buttons), 5)]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pg:{token}:{page - 1}"))
    nav.append(InlineKeyboardButton(text="❌", callback_data="close"))
    if start + PAGE_SIZE < len(items):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pg:{token}:{page + 1}"))
    rows.append(nav)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------- buyruqlar ----------------
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(texts.START.format(name=html.escape(message.from_user.first_name)))


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(texts.HELP)


@router.message(Command("privacy"))
async def privacy(message: Message):
    await message.answer(texts.PRIVACY)


@router.message(Command("terms"))
async def terms(message: Message):
    await message.answer(texts.TERMS)


@router.message(Command("delete_me"))
async def delete_me(message: Message):
    await db.delete_user(message.from_user.id)
    seen_users.discard(message.from_user.id)
    await message.answer(
        "🗑 Ma'lumotlaringiz bazadan o'chirildi.\n"
        "Botdan qayta foydalansangiz, siz yana ro'yxatga olinasiz."
    )


# ---------------- majburiy obuna ----------------
@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot):
    missing = await is_subscribed(bot, call.from_user.id)
    if missing:
        await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=subscribe_kb(missing))
        except TelegramBadRequest:
            pass
        return
    await call.answer("✅ Rahmat!")
    await call.message.edit_text("✅ Obuna tasdiqlandi! Endi qo'shiq nomini yozing 🎵")


@router.chat_join_request()
async def join_request(req: ChatJoinRequest):
    # Yopiq kanalga so'rov yuborganlar ham obuna bo'lgan deb hisoblanadi
    channels = {ch["chat_id"] for ch in await db.get_channels()}
    if req.chat.id in channels:
        await db.add_join_request(req.chat.id, req.from_user.id)


# ---------------- qidiruv va yuklash ----------------
async def deliver(message: Message, bot: Bot, key: str, url: str):
    me = await bot.me()
    cached = await db.get_cached(key)
    if cached:
        await message.answer_audio(cached, caption=f"🤖 @{me.username}")
        return

    if key in _in_progress:
        await message.answer("⏳ Bu qo'shiq hozir yuklanmoqda, bir necha soniyadan so'ng qayta bosing.")
        return

    status = await message.answer("⏳ Yuklanmoqda...")
    _in_progress.add(key)
    info = None
    try:
        async with download_limit:
            info = await music.download(url)
        if os.path.getsize(info["path"]) > MAX_FILE_SIZE:
            await status.edit_text("❗️ Fayl hajmi juda katta (50 MB dan ortiq).")
            return
        sent = await message.answer_audio(
            FSInputFile(info["path"]),
            title=info["title"][:64],
            performer=info["performer"][:64],
            duration=info["duration"],
            caption=f"🤖 @{me.username}",
        )
        await db.set_cached(key, sent.audio.file_id)
        await status.delete()
    except music.TooLong:
        await status.edit_text("❗️ Bu audio juda uzun. Qisqaroq qo'shiqni tanlang.")
    except Exception as e:  # noqa: BLE001
        log.warning("Yuklash xatosi (%s): %s", url, e)
        await status.edit_text("⚠️ Yuklab bo'lmadi. Boshqa natijani tanlab ko'ring.")
    finally:
        _in_progress.discard(key)
        if info and os.path.exists(info["path"]):
            os.remove(info["path"])


@router.message(F.text.func(music.YT_LINK.search), StateFilter(None))
async def youtube_link(message: Message, bot: Bot):
    video_id = music.YT_LINK.search(message.text).group(1)
    await deliver(message, bot, f"yt:{video_id}", f"https://www.youtube.com/watch?v={video_id}")


@router.message(F.text, ~F.text.startswith("/"), StateFilter(None))
async def search(message: Message):
    query = " ".join(message.text.split())[:100]
    if len(query) < 2:
        await message.answer("✍️ Qo'shiq nomini to'liqroq yozing.")
        return
    wait = await message.answer("🔎 Qidirilmoqda...")
    try:
        items = await music.search(query)
    except Exception as e:  # noqa: BLE001
        log.warning("Qidiruv xatosi: %s", e)
        await wait.edit_text("⚠️ Qidirishda xatolik yuz berdi. Birozdan so'ng urinib ko'ring.")
        return
    if not items:
        await wait.edit_text("😔 Hech narsa topilmadi. Boshqacha yozib ko'ring.")
        return
    text, kb = _page(_store(query, items), 0)
    await wait.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("pg:"))
async def paginate(call: CallbackQuery):
    _, token, page = call.data.split(":")
    if token not in _results:
        await call.answer("Natijalar eskirgan, qaytadan qidiring.", show_alert=True)
        return
    text, kb = _page(token, int(page))
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("dl:"))
async def download(call: CallbackQuery, bot: Bot):
    _, token, idx = call.data.split(":")
    data = _results.get(token)
    if not data:
        await call.answer("Natijalar eskirgan, qaytadan qidiring.", show_alert=True)
        return
    item = data["items"][int(idx)]
    await call.answer("⏳")
    await deliver(call.message, bot, item["key"], item["url"])


@router.callback_query(F.data == "close")
async def close(call: CallbackQuery):
    try:
        await call.message.delete()
    except TelegramBadRequest:
        await call.answer()


@router.message(StateFilter(None))
async def other(message: Message):
    await message.answer("✍️ Qo'shiq nomini matn ko'rinishida yuboring. Yordam: /help")

