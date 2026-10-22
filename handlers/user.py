import asyncio
import html
import logging
import os
import secrets
from collections import OrderedDict

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
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
from config import DOWNLOAD_DIR, MAX_FILE_SIZE
from middlewares import is_subscribed, seen_users, subscribe_kb

log = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 10
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024  # bot Telegram'dan 20 MB gacha fayl yuklay oladi
download_limit = asyncio.Semaphore(2)  # bir vaqtda nechta yuklash (bepul server uchun)
_in_progress: set[str] = set()

ROOT = os.path.dirname(os.path.dirname(__file__))
COVER_PATH = os.path.join(ROOT, "cover.jpg")
COVER_VERSION = "c2"  # muqova yoki yuklash usuli o'zgarsa oshiring — eski kesh yangilanadi
_start_photo: dict[str, str] = {}

# Qidiruv natijalari xotirada saqlanadi (token -> natijalar)
_results: "OrderedDict[str, dict]" = OrderedDict()


def _store(header: str, items: list[dict]) -> str:
    token = secrets.token_hex(4)
    _results[token] = {"header": header, "items": items}
    while len(_results) > 3000:
        _results.popitem(last=False)
    return token


def _label(it: dict) -> str:
    name = f"{it['artist']} - {it['title']}" if it.get("artist") else it["title"]
    return name


def _page(token: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    data = _results[token]
    items = data["items"]
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE

    lines = [f"{data['header']}  ·  {page + 1}/{pages}\n"]
    for i, it in enumerate(chunk, start + 1):
        mark = "🎤 " if it.get("lyrics") else ""
        lines.append(
            f"<b>{i}.</b> {mark}{html.escape(_label(it))} <i>({music.fmt_duration(it['duration'])})</i>"
        )
    if any(it.get("lyrics") for it in chunk):
        lines.append("\n🎤 — qo'shiq matni bo'yicha topilgan")

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
def start_kb(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Qanday foydalaniladi?", callback_data="how")],
        [InlineKeyboardButton(text="➕ Guruhga qo'shish", url=f"https://t.me/{username}?startgroup=start")],
    ])


@router.message(CommandStart())
async def start(message: Message, bot: Bot):
    me = await bot.me()
    caption = texts.START.format(name=html.escape(message.from_user.first_name), bot=me.username)
    photo = _start_photo.get("id") or (FSInputFile(COVER_PATH) if os.path.exists(COVER_PATH) else None)
    if photo:
        sent = await message.answer_photo(photo, caption=caption, reply_markup=start_kb(me.username))
        _start_photo["id"] = sent.photo[-1].file_id
    else:
        await message.answer(caption, reply_markup=start_kb(me.username))


@router.callback_query(F.data == "how")
async def how(call: CallbackQuery):
    await call.answer()
    await call.message.answer(texts.HELP)


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


# ---------------- yuklash va yuborish ----------------
def audio_caption(username: str) -> str:
    return f"@{username} Eng sara musiqalar shu yerda.\nQidiring, toping, tinglang va MP3 yuklab oling."


async def deliver(message: Message, bot: Bot, item: dict):
    me = await bot.me()
    base_key = item.get("key") or f"q:{item.get('query', '').lower()}"
    key = f"{COVER_VERSION}:{base_key}"
    cached = await db.get_cached(key)
    if cached:
        await message.answer_audio(cached, caption=audio_caption(me.username))
        return

    if key in _in_progress:
        await message.answer("⏳ Bu qo'shiq hozir yuklanmoqda, bir necha soniyadan so'ng qayta bosing.")
        return

    status = await message.answer(f"⏳ <b>{html.escape(_label(item))}</b>\nYuklanmoqda...")
    _in_progress.add(key)
    info = None
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
        async with download_limit:
            info = await music.download(item)
        if os.path.getsize(info["path"]) > MAX_FILE_SIZE:
            await status.edit_text("❗️ Fayl hajmi juda katta (50 MB dan ortiq).")
            return
        ext = os.path.splitext(info["path"])[1]
        sent = await message.answer_audio(
            FSInputFile(info["path"], filename=music.safe_filename(info["artist"], info["title"], ext)),
            title=info["title"][:64],
            performer=info["artist"][:64],
            duration=info["duration"],
            caption=audio_caption(me.username),
            thumbnail=FSInputFile(COVER_PATH) if os.path.exists(COVER_PATH) else None,
        )
        await db.set_cached(key, sent.audio.file_id)
        await status.delete()
    except music.TooLong:
        await status.edit_text("❗️ Bu audio juda uzun. Qisqaroq qo'shiqni tanlang.")
    except Exception as e:  # noqa: BLE001
        log.warning("Yuklash xatosi (%s): %s", _label(item), str(e)[:300])
        await status.edit_text(
            "😔 Bu qo'shiqni hozircha yuklab bo'lmadi.\n"
            "Ro'yxatdan boshqa variantni tanlang yoki nomini boshqacharoq yozib ko'ring."
        )
    finally:
        _in_progress.discard(key)
        if info and os.path.exists(info["path"]):
            os.remove(info["path"])


async def show_results(target: Message, header: str, items: list[dict]):
    text, kb = _page(_store(header, items), 0)
    await target.edit_text(text, reply_markup=kb)


# ---------------- musiqani aniqlash (Shazam) ----------------
async def recognize_and_show(status: Message, path: str):
    try:
        found = await music.recognize(path)
    except Exception as e:  # noqa: BLE001
        log.warning("Shazam xatosi: %s", e)
        found = None
    finally:
        if os.path.exists(path):
            os.remove(path)
    if not found:
        await status.edit_text(
            "😔 Bu videodagi musiqani aniqlab bo'lmadi.\n"
            "Musiqa aniq eshitiladigan qismini yuboring yoki qo'shiq nomini yozing."
        )
        return
    name = f"{found['artist']} - {found['title']}"
    await status.edit_text(f"🎧 Topildi: <b>{html.escape(name)}</b>\n🔎 Qidirilmoqda...")
    try:
        items = await music.search(name, limit=10)
    except Exception:  # noqa: BLE001
        items = []
    if not items:
        await status.edit_text(f"🎧 Topildi: <b>{html.escape(name)}</b>\n\nLekin yuklab olish uchun manba topilmadi.")
        return
    await show_results(status, f"🎧 Videodagi musiqa: <b>{html.escape(name)}</b>", items)


@router.message(F.video | F.voice | F.audio | F.video_note | F.document.mime_type.startswith("video/"))
async def media_message(message: Message, bot: Bot):
    media = message.video or message.voice or message.audio or message.video_note or message.document
    if media.file_size and media.file_size > TG_DOWNLOAD_LIMIT:
        await message.answer("❗️ Fayl juda katta (20 MB dan ortiq). Qisqaroq qismini yuboring.")
        return
    status = await message.reply("🎧 Musiqa aniqlanmoqda...")
    path = os.path.join(DOWNLOAD_DIR, f"tg_{media.file_unique_id}")
    try:
        await bot.download(media, destination=path)
    except Exception as e:  # noqa: BLE001
        log.warning("Telegram fayl yuklanmadi: %s", e)
        await status.edit_text("⚠️ Faylni olib bo'lmadi. Qaytadan yuboring.")
        return
    await recognize_and_show(status, path)


@router.message(F.text.func(music.VIDEO_LINK.search), StateFilter(None))
async def video_link(message: Message):
    url = music.VIDEO_LINK.search(message.text).group(0)
    status = await message.reply("🎧 Videodagi musiqa aniqlanmoqda...")
    try:
        path = await music.video_audio(url)
    except Exception as e:  # noqa: BLE001
        log.warning("Video havola olinmadi (%s): %s", url, str(e)[:200])
        await status.edit_text(
            "😔 Bu havoladan videoni olib bo'lmadi (yopiq akkaunt yoki sayt ruxsat bermadi).\n\n"
            "💡 Videoni telefoningizga saqlab, shu yerga <b>fayl qilib yuboring</b> — musiqani topib beraman."
        )
        return
    await recognize_and_show(status, path)


# ---------------- qidiruv ----------------
@router.message(F.text.func(music.YT_LINK.search), StateFilter(None))
async def youtube_link(message: Message, bot: Bot):
    video_id = music.YT_LINK.search(message.text).group(1)
    await deliver(message, bot, {
        "key": f"yt:{video_id}", "url": f"https://www.youtube.com/watch?v={video_id}",
        "artist": "", "title": "YouTube audio", "duration": 0,
    })


@router.message(F.text, ~F.text.startswith("/"), StateFilter(None))
async def search(message: Message, bot: Bot):
    query = " ".join(message.text.split())[:200]
    if len(query) < 2:
        await message.answer("✍️ Qo'shiq nomini to'liqroq yozing.")
        return
    wait = await message.answer("🔎 Qidirilmoqda...")
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        items = await music.search(query)
    except Exception as e:  # noqa: BLE001
        log.warning("Qidiruv xatosi: %s", e)
        await wait.edit_text("⚠️ Qidirishda xatolik yuz berdi. Birozdan so'ng urinib ko'ring.")
        return
    if not items:
        await wait.edit_text(
            "😔 Hech narsa topilmadi.\n\n"
            "💡 Maslahat: <i>Ijrochi - Qo'shiq nomi</i> ko'rinishida yozing yoki qo'shiqdan bir qator matn yozing."
        )
        return
    await show_results(wait, f"🔎 <b>{html.escape(query[:60])}</b>", items)


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
    await call.answer("⏳")
    await deliver(call.message, bot, data["items"][int(idx)])


@router.callback_query(F.data == "close")
async def close(call: CallbackQuery):
    try:
        await call.message.delete()
    except TelegramBadRequest:
        await call.answer()


@router.message(StateFilter(None))
async def other(message: Message):
    await message.answer("✍️ Qo'shiq nomini yozing yoki musiqasi bor video yuboring. Yordam: /help")
