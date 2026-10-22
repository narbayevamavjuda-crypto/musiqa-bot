import asyncio
import csv
import html
import io
import logging
import time

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import db
from config import ADMINS
from middlewares import banned_users, reset_sub_cache

log = logging.getLogger(__name__)
router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))

BTN_STATS = "📊 Statistika"
BTN_ADS = "📢 Reklama yuborish"
BTN_CHANNELS = "📋 Kanallar"
BTN_ADD_CH = "➕ Kanal qo'shish"
BTN_BAN = "🚫 Ban / Unban"
BTN_EXPORT = "📥 Foydalanuvchilar (CSV)"
BTN_EXIT = "🚪 Paneldan chiqish"
BTN_CANCEL = "❌ Bekor qilish"

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_STATS), KeyboardButton(text=BTN_ADS)],
        [KeyboardButton(text=BTN_CHANNELS), KeyboardButton(text=BTN_ADD_CH)],
        [KeyboardButton(text=BTN_BAN), KeyboardButton(text=BTN_EXPORT)],
        [KeyboardButton(text=BTN_EXIT)],
    ],
    resize_keyboard=True,
)
cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


class AdminState(StatesGroup):
    ad_message = State()
    ad_choice = State()
    ad_buttons = State()
    ad_confirm = State()
    channel = State()
    ban = State()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👨‍💻 <b>Admin panel</b>", reply_markup=admin_kb)


@router.message(F.text == BTN_CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=admin_kb)


@router.message(F.text == BTN_EXIT)
async def exit_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Paneldan chiqdingiz. Qaytish: /admin", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == BTN_STATS)
async def stats(message: Message):
    s = await db.stats()
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{s['total']}</b>\n"
        f"✅ Faol: <b>{s['active']}</b>\n"
        f"💤 Botni bloklagan: <b>{s['total'] - s['active']}</b>\n"
        f"🚫 Ban qilingan: <b>{s['banned']}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{s['today']}</b>\n"
        f"🎵 Keshdagi qo'shiqlar: <b>{s['songs']}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(await db.get_channels())}</b>"
    )


@router.message(F.text == BTN_EXPORT)
async def export_users(message: Message):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "full_name", "username", "joined", "active", "banned"])
    for u in await db.all_users():
        writer.writerow([u["id"], u["full_name"], u["username"] or "", u["joined"], u["active"], u["banned"]])
    data = buf.getvalue().encode("utf-8-sig")  # Excel o'zbek harflarini to'g'ri ochishi uchun
    await message.answer_document(BufferedInputFile(data, "users.csv"), caption="📥 Foydalanuvchilar ro'yxati")


# =====================================================================
#                 REKLAMA (hammaga xabar yuborish)
# =====================================================================
_broadcast = {"running": False, "stop": False}


@router.message(F.text == BTN_ADS)
async def ads_start(message: Message, state: FSMContext):
    if _broadcast["running"]:
        await message.answer("⏳ Hozir boshqa reklama yuborilmoqda. Tugashini kuting.")
        return
    await state.set_state(AdminState.ad_message)
    await message.answer(
        "📢 Reklama xabarini yuboring.\n\n"
        "Matn, rasm, video, audio, fayl, GIF — istalgan turdagi xabar bo'lishi mumkin. "
        "Kanal postini forward qilsangiz ham bo'ladi.",
        reply_markup=cancel_kb,
    )


@router.message(AdminState.ad_message)
async def ads_got_message(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.chat.id, msg_id=message.message_id, buttons=None)
    await state.set_state(AdminState.ad_choice)
    await message.answer(
        "Xabar ostiga havola tugmalari qo'shasizmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="ad_btn"),
            InlineKeyboardButton(text="➡️ Tugmasiz", callback_data="ad_nobtn"),
        ]]),
    )


@router.callback_query(AdminState.ad_choice, F.data == "ad_btn")
async def ads_ask_buttons(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.ad_buttons)
    await call.message.edit_text(
        "Tugmalarni quyidagi ko'rinishda yuboring:\n\n"
        "<code>Kanalga o'tish - https://t.me/kanal</code>\n"
        "<code>Sayt - https://example.com | Instagram - https://instagram.com/x</code>\n\n"
        "Har bir qator — alohida qator tugmalar. Bir qatorga bir nechta tugma uchun <code>|</code> qo'ying."
    )


def _parse_buttons(text: str) -> list[list[dict]] | None:
    rows = []
    for line in text.strip().splitlines():
        row = []
        for part in line.split("|"):
            if " - " not in part:
                return None
            title, url = (x.strip() for x in part.rsplit(" - ", 1))
            if not title or not url.startswith(("http://", "https://", "tg://")):
                return None
            row.append({"text": title, "url": url})
        if row:
            rows.append(row)
    return rows or None


def _markup(buttons) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**b) for b in row] for row in buttons])


@router.message(AdminState.ad_buttons, F.text)
async def ads_got_buttons(message: Message, state: FSMContext, bot: Bot):
    buttons = _parse_buttons(message.text)
    if not buttons:
        await message.answer("❗️ Format noto'g'ri. Namuna: <code>Matn - https://link</code>")
        return
    await state.update_data(buttons=buttons)
    await _preview(message, state, bot)


@router.callback_query(AdminState.ad_choice, F.data == "ad_nobtn")
async def ads_no_buttons(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.message.delete()
    await _preview(call.message, state, bot)


async def _preview(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.set_state(AdminState.ad_confirm)
    await bot.copy_message(message.chat.id, data["chat_id"], data["msg_id"], reply_markup=_markup(data["buttons"]))
    count = len(await db.all_user_ids())
    await message.answer(
        f"☝️ Reklama shunday ko'rinadi. <b>{count}</b> ta foydalanuvchiga yuborilsinmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yuborish", callback_data="ad_send"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel"),
        ]]),
    )


@router.callback_query(F.data == "ad_cancel")
async def ads_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Reklama bekor qilindi.")
    await call.message.answer("Admin panel", reply_markup=admin_kb)


@router.callback_query(AdminState.ad_confirm, F.data == "ad_send")
async def ads_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    if _broadcast["running"]:
        await call.answer("Boshqa reklama yuborilmoqda!", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await call.message.edit_text("🚀 Reklama yuborish boshlandi...")
    await call.message.answer("Admin panel", reply_markup=admin_kb)
    asyncio.create_task(_run_broadcast(bot, call.message, data))


@router.callback_query(F.data == "bc_stop")
async def ads_stop(call: CallbackQuery):
    _broadcast["stop"] = True
    await call.answer("⏹ To'xtatilmoqda...")


async def _run_broadcast(bot: Bot, status: Message, data: dict):
    _broadcast.update(running=True, stop=False)
    users = await db.all_user_ids()
    markup = _markup(data["buttons"])
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏹ To'xtatish", callback_data="bc_stop")]])
    ok = blocked = failed = 0
    last_edit = 0.0

    def report(title: str) -> str:
        done = ok + blocked + failed
        return (
            f"{title}\n\n"
            f"📊 {done} / {len(users)}\n"
            f"📨 Yetkazildi: <b>{ok}</b>\n"
            f"🚫 Botni bloklagan: <b>{blocked}</b>\n"
            f"⚠️ Xatolik: <b>{failed}</b>"
        )

    try:
        for uid in users:
            if _broadcast["stop"]:
                break
            while True:
                try:
                    await bot.copy_message(uid, data["chat_id"], data["msg_id"], reply_markup=markup)
                    ok += 1
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                    continue
                except TelegramForbiddenError:
                    await db.set_inactive(uid)
                    blocked += 1
                except TelegramBadRequest as e:
                    if "chat not found" in str(e).lower():
                        await db.set_inactive(uid)
                        blocked += 1
                    else:
                        failed += 1
                except Exception as e:  # noqa: BLE001
                    log.warning("Reklama %s ga yuborilmadi: %s", uid, e)
                    failed += 1
                break
            await asyncio.sleep(0.05)  # Telegram limiti ~25 xabar/soniya
            if time.monotonic() - last_edit > 5:
                last_edit = time.monotonic()
                try:
                    await status.edit_text(report("🚀 Reklama yuborilmoqda..."), reply_markup=stop_kb)
                except TelegramBadRequest:
                    pass
    finally:
        _broadcast["running"] = False
        title = "⏹ <b>Reklama to'xtatildi</b>" if _broadcast["stop"] else "✅ <b>Reklama yuborildi!</b>"
        try:
            await status.edit_text(report(title))
        except TelegramBadRequest:
            await status.answer(report(title))


# =====================================================================
#                 MAJBURIY OBUNA KANALLARI
# =====================================================================
@router.message(F.text == BTN_CHANNELS)
async def channels_list(message: Message):
    channels = await db.get_channels()
    if not channels:
        await message.answer("Majburiy obuna kanallari yo'q. «➕ Kanal qo'shish» tugmasini bosing.")
        return
    text = "📋 <b>Majburiy obuna kanallari</b>\n\n" + "\n".join(
        f"{i}. <a href='{ch['link']}'>{html.escape(ch['title'])}</a> (<code>{ch['chat_id']}</code>)"
        for i, ch in enumerate(channels, 1)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {ch['title']}", callback_data=f"delch:{ch['id']}")] for ch in channels
    ])
    await message.answer(text + "\n\nO'chirish uchun bosing 👇", reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("delch:"))
async def channel_delete(call: CallbackQuery):
    await db.delete_channel(int(call.data.split(":")[1]))
    reset_sub_cache()
    await call.answer("🗑 Kanal o'chirildi")
    await call.message.delete()


@router.message(F.text == BTN_ADD_CH)
async def channel_add_start(message: Message, state: FSMContext):
    await state.set_state(AdminState.channel)
    await message.answer(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "1️⃣ Botni kanalga <b>admin</b> qiling (\"Foydalanuvchilarni qo'shish\" huquqi bilan).\n"
        "2️⃣ So'ng quyidagilardan birini yuboring:\n"
        "• kanal username: <code>@kanalim</code>\n"
        "• kanal ID: <code>-1001234567890</code>\n"
        "• yoki kanaldan istalgan postni shu yerga <b>forward</b> qiling.\n\n"
        "🔒 Yopiq kanal uchun bot «qo'shilish so'rovi» havolasini o'zi yaratadi — "
        "so'rov yuborgan foydalanuvchi ham obuna bo'lgan hisoblanadi.",
        reply_markup=cancel_kb,
    )


@router.message(AdminState.channel)
async def channel_add(message: Message, state: FSMContext, bot: Bot):
    chat_ref: int | str | None = None
    if message.forward_from_chat:
        chat_ref = message.forward_from_chat.id
    elif message.text:
        t = message.text.strip()
        if "t.me/" in t:
            t = "@" + t.split("t.me/", 1)[1].split("/")[0]
        chat_ref = int(t) if t.lstrip("-").isdigit() else t
    if chat_ref is None:
        await message.answer("❗️ Username, ID yuboring yoki postni forward qiling.")
        return

    try:
        chat = await bot.get_chat(chat_ref)
        me = await bot.get_chat_member(chat.id, bot.id)
    except (TelegramBadRequest, TelegramForbiddenError):
        await message.answer("❗️ Kanal topilmadi yoki bot kanalga qo'shilmagan. Qayta urinib ko'ring.")
        return
    if chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP):
        await message.answer("❗️ Bu kanal yoki guruh emas.")
        return
    if me.status != ChatMemberStatus.ADMINISTRATOR:
        await message.answer("❗️ Bot bu kanalda admin emas. Avval botni admin qiling.")
        return

    if chat.username:
        link = f"https://t.me/{chat.username}"
    else:
        try:
            invite = await bot.create_chat_invite_link(chat.id, name="Majburiy obuna (bot)", creates_join_request=True)
            link = invite.invite_link
        except TelegramBadRequest:
            await message.answer("❗️ Havola yaratib bo'lmadi. Botga «Foydalanuvchilarni qo'shish» huquqini bering.")
            return

    await db.add_channel(chat.id, chat.title or "Kanal", link)
    reset_sub_cache()
    await state.clear()
    await message.answer(f"✅ <b>{html.escape(chat.title or '')}</b> majburiy obunaga qo'shildi!", reply_markup=admin_kb)


# =====================================================================
#                 BAN / UNBAN
# =====================================================================
@router.message(F.text == BTN_BAN)
async def ban_start(message: Message, state: FSMContext):
    await state.set_state(AdminState.ban)
    await message.answer(
        "Foydalanuvchi ID raqamini yuboring (ban qilingan bo'lsa — bandan chiqariladi).\n"
        "Yoki shu foydalanuvchining xabarini forward qiling.\n\n"
        "Tezkor buyruqlar: <code>/ban 123456</code>, <code>/unban 123456</code>",
        reply_markup=cancel_kb,
    )


async def _set_ban(message: Message, user_id: int, banned: bool):
    if user_id in ADMINS:
        await message.answer("❗️ Adminni ban qilib bo'lmaydi.")
        return
    if not await db.set_banned(user_id, banned):
        await message.answer("❗️ Bu foydalanuvchi bazada topilmadi.")
        return
    (banned_users.add if banned else banned_users.discard)(user_id)
    await message.answer(
        f"🚫 <code>{user_id}</code> ban qilindi." if banned else f"✅ <code>{user_id}</code> bandan chiqarildi.",
        reply_markup=admin_kb,
    )


@router.message(AdminState.ban)
async def ban_toggle(message: Message, state: FSMContext):
    if message.forward_from:
        user_id = message.forward_from.id
    elif message.text and message.text.strip().isdigit():
        user_id = int(message.text.strip())
    else:
        await message.answer("❗️ ID raqam yuboring (foydalanuvchi forward'ni yashirgan bo'lishi mumkin).")
        return
    await state.clear()
    await _set_ban(message, user_id, user_id not in banned_users)


@router.message(Command("ban", "unban"))
async def ban_cmd(message: Message, command: CommandObject):
    if not command.args or not command.args.strip().isdigit():
        await message.answer(f"Foydalanish: <code>/{command.command} 123456</code>")
        return
    await _set_ban(message, int(command.args.strip()), command.command == "ban")
