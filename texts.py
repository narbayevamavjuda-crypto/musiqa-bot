from config import ADMIN_CONTACT

CONTACT = ADMIN_CONTACT or "bot administratori"

START = (
    "👋 Assalomu alaykum, <b>{name}</b>!\n"
    "🎶 <b>MusiqaTop</b> ga xush kelibsiz — sevimli qo'shiqlaringiz endi bir qadam narida!\n\n"
    "✨ <b>Men nimalar qila olaman:</b>\n"
    "🔎 Qo'shiq yoki ijrochi nomini yozing — topib beraman\n"
    "🎤 Qo'shiqdan bir qator <b>matn</b> yozing — qaysi qo'shiq ekanini aniqlayman\n"
    "🎬 Instagram, TikTok havolasi yoki <b>video</b> yuboring — undagi musiqani topaman\n"
    "🎙 Ovozli xabar yuboring — eshitib, qo'shiqni aniqlayman\n"
    "🎧 Har bir qo'shiq sifatli audio ko'rinishida keladi\n\n"
    "👇 Qani, boshladik! Birinchi qo'shiq nomini yozing.\n\n"
    "<i>Botdan foydalanib, /terms va /privacy shartlariga rozilik bildirasiz.</i>"
)

HELP = (
    "📖 <b>Qanday foydalaniladi?</b>\n\n"
    "1️⃣ <b>Nomi bo'yicha:</b> <i>Shahzoda - Ayt</i> deb yozing → ro'yxatdan raqamni tanlang.\n"
    "2️⃣ <b>Matni bo'yicha:</b> qo'shiqdan esingizdagi bir qatorni yozing (kamida 4 so'z). "
    "🎤 belgili natijalar matn bo'yicha topilgan.\n"
    "3️⃣ <b>Videodan:</b> Instagram/TikTok havolasini yoki videoni o'zini yuboring.\n"
    "4️⃣ <b>Ovozdan:</b> qo'shiq yangrayotgan joyda ovozli xabar yozib yuboring.\n"
    "5️⃣ <b>YouTube havolasi:</b> yuborsangiz to'g'ridan-to'g'ri audio qilib beraman.\n\n"
    "⬅️ ➡️ — boshqa natijalar\n\n"
    "<b>Buyruqlar:</b>\n"
    "/start — bosh sahifa\n"
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
    "1. Bot ochiq internet manbalaridagi (YouTube, SoundCloud) audiolarni qidirib beradi va Shazam orqali musiqani aniqlaydi. "
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
