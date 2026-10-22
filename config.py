import hashlib
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMINS = {int(x) for x in os.getenv("ADMINS", "").replace(" ", "").split(",") if x}

# Admin bilan bog'lanish (@username) — maxfiylik siyosati va shikoyatlar uchun
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "").strip()

# Baza: DATABASE_URL berilsa — PostgreSQL (Neon), aks holda lokal SQLite fayl
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
MAX_DURATION = int(os.getenv("MAX_DURATION", 15 * 60))  # sekund
MAX_FILE_SIZE = 49 * 1024 * 1024  # Telegram bot limiti 50 MB

# Webhook rejimi: Render RENDER_EXTERNAL_URL ni o'zi beradi.
# Bo'sh bo'lsa bot polling rejimida ishlaydi (kompyuterda sinash uchun).
BASE_URL = (os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]

# YouTube cookies (ixtiyoriy): Render "Secret Files" ga cookies.txt qo'shilsa avtomatik ishlatiladi
COOKIES_FILE = next(
    (p for p in (os.getenv("COOKIES_FILE", ""), "/etc/secrets/cookies.txt", "cookies.txt") if p and os.path.exists(p)),
    "",
)

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN topilmadi! .env faylini yoki hosting sozlamalarini to'ldiring.")
