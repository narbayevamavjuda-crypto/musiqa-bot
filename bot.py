import asyncio
import html
import logging
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent

import db
import middlewares
import music
from config import ADMINS, BASE_URL, BOT_TOKEN, COOKIES_FILE, PORT, WEBHOOK_PATH, WEBHOOK_SECRET
from handlers import admin, user

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("musiqa_bot")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

USER_COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="terms", description="Foydalanish shartlari"),
    BotCommand(command="privacy", description="Maxfiylik siyosati"),
]


def setup_dispatcher():
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(middlewares.ThrottlingMiddleware(rate=0.7))
        observer.outer_middleware(middlewares.UserMiddleware())
        observer.middleware(middlewares.SubscriptionMiddleware())
    dp.include_router(admin.router)  # admin router birinchi bo'lishi shart
    dp.include_router(user.router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)


@dp.errors()
async def on_error(event: ErrorEvent):
    log.exception("Kutilmagan xato", exc_info=event.exception)
    tb = "".join(traceback.format_exception(event.exception))[-3000:]
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, f"⚠️ <b>Botda xato:</b>\n<pre>{html.escape(tb)}</pre>")
        except Exception:  # noqa: BLE001
            pass
        break  # faqat birinchi adminga


async def keep_alive():
    """Render bepul tarifida bot uxlab qolmasligi uchun o'z manziliga har 10 daqiqada murojaat qiladi."""
    import aiohttp

    await asyncio.sleep(60)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=30)) as r:
                    log.debug("keep-alive: %s", r.status)
            except Exception as e:  # noqa: BLE001
                log.warning("keep-alive xatosi: %s", e)
            await asyncio.sleep(600)


async def on_startup():
    await db.init()
    middlewares.banned_users.update(await db.banned_ids())

    # YouTube cookies: avval bazadan, bo'lmasa Render "Secret Files" dagi cookies.txt dan
    cookies = await db.get_setting("yt_cookies")
    if not cookies and COOKIES_FILE:
        with open(COOKIES_FILE, encoding="utf-8", errors="ignore") as f:
            cookies = f.read()
    music.set_cookies(cookies)
    log.info("YouTube cookies: %s", "bor" if cookies else "yo'q")

    try:
        await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
        await bot.set_my_short_description("🎶 Qo'shiq nomi, matni yoki videosini yuboring — musiqani topib beraman!")
        await bot.set_my_description(
            "🎶 MusiqaTop — eng sara musiqalar shu yerda!\n\n"
            "🔎 Qo'shiq nomi yoki ijrochini yozing\n"
            "🎤 Qo'shiqdan bir qator matn yozing\n"
            "🎬 Instagram/TikTok video yoki ovozli xabar yuboring\n"
            "— bot musiqani topib, sifatli audio qilib yuboradi.\n\n"
            "Shartlar: /terms · Maxfiylik: /privacy"
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Bot ma'lumotlarini o'rnatib bo'lmadi: %s", e)
    for admin_id in ADMINS:
        try:
            await bot.set_my_commands(
                USER_COMMANDS + [BotCommand(command="admin", description="👨‍💻 Admin panel")],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception:  # noqa: BLE001
            pass  # admin hali botga /start bosmagan

    if BASE_URL:
        await bot.set_webhook(
            f"{BASE_URL}{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
        )
        asyncio.create_task(keep_alive())
        log.info("Webhook o'rnatildi: %s%s", BASE_URL, WEBHOOK_PATH)
    me = await bot.me()
    log.info("@%s ishga tushdi. Adminlar: %s", me.username, ADMINS)


async def on_shutdown():
    await db.close()


def run_webhook():
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    async def health(_):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)


async def run_polling():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    setup_dispatcher()
    if BASE_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
