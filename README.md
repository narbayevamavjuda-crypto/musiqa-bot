# 🎵 Musiqa bot (Telegram)

Foydalanuvchi qo'shiq nomini yozadi → bot YouTube'dan (zaxira: SoundCloud) qidiradi → tanlangan qo'shiqni audio qilib yuboradi.

## Imkoniyatlar

**Foydalanuvchi uchun**
- 🔎 Qidiruv: 30 tagacha natija, ⬅️ ➡️ bilan sahifalash
- 🔗 YouTube havolasini yuborsa, to'g'ridan-to'g'ri yuklaydi
- ⚡️ Yuklangan qo'shiqlar keshlanadi — keyingi safar bir zumda yuboriladi
- 📜 `/terms` (foydalanish shartlari), 🔐 `/privacy` (maxfiylik siyosati), 🗑 `/delete_me` (ma'lumotlarni o'chirish) — Telegram qoidalari talab qiladi

**Admin uchun** (`/admin`)
| Tugma | Vazifasi |
|---|---|
| 📢 Reklama yuborish | Istalgan xabar (matn/rasm/video/forward) + havola tugmalari → ko'rib chiqish → hammaga yuborish. Jarayon ko'rinib turadi, ⏹ bilan to'xtatsa bo'ladi |
| ➕ Kanal qo'shish | Majburiy obuna kanali. Ochiq va yopiq kanallar ("qo'shilish so'rovi" bilan) qo'llab-quvvatlanadi |
| 📋 Kanallar | Ro'yxat va 🗑 o'chirish |
| 🚫 Ban / Unban | Foydalanuvchini bloklash (`/ban ID`, `/unban ID`) |
| 📊 Statistika | Jami, faol, bloklagan, bugungi foydalanuvchilar |
| 📥 Foydalanuvchilar (CSV) | Excel'da ochiladigan ro'yxat |

**Himoya:** flooddan himoya, botda xato bo'lsa adminga xabar keladi, botni bloklaganlar avtomatik belgilanadi.

---

# 🚀 Internetga joylash (bepul, kartasiz, faqat Google akkaunt bilan)

Kerak bo'ladigan 3 ta bepul xizmat (hammasiga **Google akkaunt** bilan kiriladi, karta so'ralmaydi):

| Xizmat | Nima uchun |
|---|---|
| **GitHub** | Bot kodini saqlash |
| **Neon.tech** | Baza (foydalanuvchilar, kanallar) — umrbod bepul |
| **Render.com** | Botni 24/7 ishlatish — umrbod bepul |

## 1-qadam. Bot tokeni va ID
1. [@BotFather](https://t.me/BotFather) → `/newbot` → token oling.
2. [@userinfobot](https://t.me/userinfobot) → o'z ID raqamingizni oling.

## 2-qadam. GitHub'ga kodni yuklash
1. https://github.com/signup — Google akkauntingizdagi Gmail bilan ro'yxatdan o'ting.
2. Yuqori o'ngdagi **+** → **New repository** → nom: `musiqa-bot` → **Public** → **Create repository**.
3. Ochilgan sahifada **"uploading an existing file"** havolasini bosing va loyiha fayllarini (`.venv` papkasidan tashqari) sudrab tashlang → **Commit changes**.

> ⚠️ `.env` faylini HECH QACHON GitHub'ga yuklamang — tokeningiz o'g'irlanadi!

## 3-qadam. Neon — bepul baza
1. https://neon.tech → **Sign up** → **Continue with Google**.
2. Loyiha yarating (nom: `musiqa-bot`, region: **Europe (Frankfurt)**).
3. **Connect** tugmasini bosing → `postgresql://...` bilan boshlanadigan manzilni nusxalang.

## 4-qadam. Render — botni ishga tushirish
1. https://render.com → **Get Started** → **Google** bilan kiring.
2. **New +** → **Web Service** → **Public Git Repository** → GitHub'dagi repo havolangizni qo'ying (masalan `https://github.com/username/musiqa-bot`) → **Connect**.
3. Sozlamalar:
   - **Language:** Docker (o'zi aniqlaydi)
   - **Region:** Frankfurt
   - **Instance Type:** **Free**
4. **Environment Variables** bo'limiga qo'shing:

   | Key | Value |
   |---|---|
   | `BOT_TOKEN` | BotFather'dan olgan token |
   | `ADMINS` | ID raqamingiz (bir nechta bo'lsa vergul bilan) |
   | `ADMIN_CONTACT` | `@username`ingiz |
   | `DATABASE_URL` | Neon'dan olgan manzil |

5. **Deploy Web Service** → 3–5 daqiqa kuting. Logda `ishga tushdi` yozuvi chiqsa — tayyor! ✅

Botga `/start` yozing, keyin `/admin`.

### Bot uxlab qolmaydimi?
Render bepul tarifida 15 daqiqa so'rov bo'lmasa server uxlaydi. Bot **o'zini har 10 daqiqada uyg'otib turadi**, shuning uchun 24/7 ishlaydi. Qo'shimcha kafolat uchun (ixtiyoriy): https://cron-job.org da bepul akkaunt ochib, har 10 daqiqada `https://SIZNING-BOT.onrender.com/health` manzilini chaqiradigan vazifa qo'shing.

Bepul tarif oyiga 750 soat beradi — bitta bot uchun to'liq oy (744 soat) yetadi. **Faqat bitta** bepul web service yarating.

---

## ❓ Muammolar

**"Yuklab bo'lmadi" ko'p chiqsa** — YouTube server IP manzillarini ba'zan bloklaydi. Bot o'zi SoundCloud'ga o'tadi, lekin YouTube'ni tiklash uchun:
1. Kompyuteringizda brauzerga **"Get cookies.txt LOCALLY"** kengaytmasini o'rnating.
2. YouTube'ga (ikkinchi, keraksiz Google akkaunt bilan!) kiring → kengaytma orqali `cookies.txt` ni yuklab oling.
3. Render → servisingiz → **Environment** → **Secret Files** → nomi `cookies.txt`, ichiga fayl matnini qo'ying → Save.

**Kanal qo'shilmayapti** — bot kanalda admin bo'lishi va "Foydalanuvchilarni qo'shish" huquqiga ega bo'lishi kerak.

**Kodni yangilash** — GitHub'da faylni almashtirsangiz, Render avtomatik qayta joylaydi.

## 💻 Kompyuterda sinash
`.env.example` → `.env` qilib to'ldiring (`DATABASE_URL` bo'sh qolsa, lokal `bot.db` ishlatiladi) va `ishga_tushirish.bat` ni bosing.

> ⚠️ Bir token bilan bot faqat bitta joyda ishlay oladi. Render'da ishlayotgan bo'lsa, kompyuterda ishga tushirmang (yoki aksincha).
