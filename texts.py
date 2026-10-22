from config import ADMIN_CONTACT

CONTACT = ADMIN_CONTACT or "bot administratori"

START = (
    "👋 Salom, <b>{name}</b>!\n\n"
    "🎵 Men musiqa topib beruvchi botman.\n"
    "Qo'shiq nomi yoki ijrochi ismini yozing — topib, audio qilib yuboraman.\n"
    "YouTube havolasini yuborsangiz ham bo'ladi.\n\n"
    "Masalan: <i>Shahzoda - Ayt</i>\n\n"
    "ℹ️ Botdan foydalanish orqali siz /terms (foydalanish shartlari) va "
    "/privacy (maxfiylik siyosati) ga rozilik bildirasiz."
)

HELP = (
    "📖 <b>Yordam</b>\n\n"
    "🔎 Qo'shiq nomini yozing → ro'yxatdan raqamni tanlang → audio keladi.\n"
    "⬅️ ➡️ tugmalari bilan boshqa natijalarni ko'rish mumkin.\n"
    "🔗 YouTube havolasini yuborsangiz, to'g'ridan-to'g'ri yuklab beraman.\n\n"
    "<b>Buyruqlar:</b>\n"
    "/start — botni qayta ishga tushirish\n"
    "/help — yordam\n"
    "/terms — foydalanish shartlari\n"
    "/privacy — maxfiylik siyosati\n"
    "/delete_me — ma'lumotlarimni o'chirish\n\n"
    f"📩 Aloqa: {CONTACT}"
)

PRIVACY = (
    "🔐 <b>Maxfiylik siyosati</b>\n\n"
    "<b>1. Qanday ma'lumotlar saqlanadi:</b> Telegram ID raqamingiz, ismingiz, "
    "username'ingiz va botga birinchi kirgan sanangiz. Bot sizning telefon raqamingiz, "
    "yozishmalaringiz yoki boshqa shaxsiy ma'lumotlaringizni so'ramaydi va saqlamaydi.\n\n"
    "<b>2. Nima uchun:</b> botning ishlashi, statistika, kanallarga obunani tekshirish "
    "va bot yangiliklari/e'lonlarini yuborish uchun.\n\n"
    "<b>3. Uchinchi shaxslarga berilmaydi.</b> Ma'lumotlar sotilmaydi va boshqalarga uzatilmaydi.\n\n"
    "<b>4. Qidiruv so'rovlaringiz</b> saqlanmaydi — faqat qo'shiq topish uchun ishlatiladi.\n\n"
    "<b>5. O'chirish:</b> /delete_me buyrug'i orqali ma'lumotlaringizni istalgan vaqtda "
    "o'chirishingiz mumkin. Botdan foydalanishni to'xtatish uchun uni bloklash kifoya.\n\n"
    f"📩 Savollar bo'yicha: {CONTACT}"
)

TERMS = (
    "📜 <b>Foydalanish shartlari</b>\n\n"
    "1. Bot ochiq internet manbalaridagi (YouTube, SoundCloud) audiolarni qidirib beradi. "
    "Bot hech qanday audio faylning muallifi yoki egasi emas.\n\n"
    "2. Yuklangan audiolar faqat <b>shaxsiy tinglash</b> uchun. Ularni tijorat maqsadida "
    "tarqatish mualliflik huquqini buzishi mumkin — bunga foydalanuvchi o'zi javobgar.\n\n"
    "3. <b>Mualliflik huquqi egalari</b> o'z asarlarini botdan olib tashlashni so'rasa, "
    f"{CONTACT} ga murojaat qilsin — so'rov tez ko'rib chiqiladi.\n\n"
    "4. Botni spam, flood yoki zararli maqsadlarda ishlatish taqiqlanadi. "
    "Qoidabuzarlar ogohlantirishsiz bloklanadi.\n\n"
    "5. Bot e'lon va reklama xabarlarini yuborishi mumkin.\n\n"
    "6. Bot \"boricha\" taqdim etiladi; texnik sabablarga ko'ra vaqtincha ishlamasligi mumkin."
)

SUBSCRIBE = (
    "❗️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling, "
    "so'ng <b>✅ Tekshirish</b> tugmasini bosing:"
)

BANNED = "🚫 Siz botdan foydalanishdan chetlatilgansiz."
