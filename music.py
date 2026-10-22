"""Qo'shiq qidirish, yuklash va aniqlash.

Qidiruv: YouTube (+ qo'shiq matni bo'yicha lrclib.net).
Yuklash: YouTube (cookies bilan) → zaxira: SoundCloud (faqat to'liq, himoyalanmagan treklar).
Aniqlash: Shazam (video, ovozli xabar, Instagram/TikTok havolasi).
"""
import asyncio
import json
import logging
import os
import re
import tempfile
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

import yt_dlp
from yt_dlp.utils import match_filter_func

from config import DOWNLOAD_DIR, MAX_DURATION

log = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YT_LINK = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/)|youtu\.be/|music\.youtube\.com/watch\?v=)([\w-]{11})"
)
VIDEO_LINK = re.compile(
    r"https?://(?:www\.|m\.|vm\.|vt\.)?(?:instagram\.com|tiktok\.com|facebook\.com|fb\.watch|x\.com|twitter\.com|"
    r"likee\.video|pin\.it|pinterest\.com|vk\.com|ok\.ru|snapchat\.com|threads\.net)/\S+",
    re.I,
)

COOKIES_PATH = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
_state = {"cookies": False}


class TooLong(Exception):
    pass


class NotFound(Exception):
    pass


# ---------------- YouTube cookies ----------------
def set_cookies(text: str | None):
    """Admin yuborgan cookies.txt matnini yt-dlp uchun faylga yozadi."""
    if text:
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        _state["cookies"] = True
    else:
        if os.path.exists(COOKIES_PATH):
            os.remove(COOKIES_PATH)
        _state["cookies"] = False


def has_cookies() -> bool:
    return _state["cookies"]


def _opts(**extra) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True, "socket_timeout": 20}
    opts.update(extra)
    return opts


def _yt_opts(**extra) -> dict:
    opts = _opts(**extra)
    if _state["cookies"]:
        opts["cookiefile"] = COOKIES_PATH
    return opts


# ---------------- nomlarni tozalash ----------------
_JUNK = re.compile(
    r"\s*[\(\[\{][^\)\]\}]*(official|video|audio|klip|clip|music|lyric|mood|premyera|premiere|hd|4k|"
    r"концерт|клип|текст|tv|version|visualizer|remaster)[^\)\]\}]*[\)\]\}]",
    re.I,
)


def clean_title(raw: str, channel: str = "") -> tuple[str, str]:
    """'Shahzoda - Ayt (Official Video) | Шахзода' -> ('Shahzoda', 'Ayt')."""
    t = re.split(r"\s+[|/]\s+|\s+//\s+", raw or "")[0]
    t = _JUNK.sub("", t)
    t = re.sub(r"\s*#\S+", "", t).strip(" -–—_")
    for sep in (" - ", " – ", " — ", " -- "):
        if sep in t:
            artist, title = t.split(sep, 1)
            return artist.strip()[:64], title.strip()[:64]
    channel = re.sub(r"\s*(-\s*Topic|VEVO|Official|Music|TV)$", "", channel or "", flags=re.I).strip()
    return channel[:64], (t or raw or "Audio")[:64]


def _similar(a: str, b: str) -> float:
    norm = lambda s: re.sub(r"[^\w]+", " ", s.lower()).strip()  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---------------- qidiruv ----------------
def _yt_search(query: str, limit: int) -> list[dict]:
    with yt_dlp.YoutubeDL(_yt_opts(extract_flat=True, skip_download=True)) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    items, seen = [], set()
    for e in info.get("entries") or []:
        if not e or not e.get("id"):
            continue
        duration = int(e.get("duration") or 0)
        if not duration or duration > MAX_DURATION or duration < 40:
            continue  # jonli efirlar, juda uzun mikslar va qisqa shorts'lar chiqarilmaydi
        artist, title = clean_title(e.get("title", ""), e.get("channel") or e.get("uploader") or "")
        sig = f"{artist.lower()}|{title.lower()}"
        if sig in seen:
            continue
        seen.add(sig)
        items.append({
            "key": f"yt:{e['id']}",
            "url": f"https://www.youtube.com/watch?v={e['id']}",
            "artist": artist,
            "title": title,
            "duration": duration,
        })
    return items


def _lyrics_search(text: str, limit: int = 5) -> list[dict]:
    """Qo'shiq matnidan parcha bo'yicha qo'shiqni topadi (lrclib.net)."""
    url = "https://lrclib.net/api/search?q=" + urllib.parse.quote(text)
    req = urllib.request.Request(url, headers={"User-Agent": "MusiqaBot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    if not isinstance(data, list):
        return []
    items, seen = [], set()
    for d in data:
        artist, title = (d.get("artistName") or "").strip(), (d.get("trackName") or "").strip()
        sig = f"{artist.lower()}|{title.lower()}"
        if not artist or not title or sig in seen:
            continue
        seen.add(sig)
        items.append({
            "key": None,  # yuklashda YouTube'dan qidirib topiladi
            "query": f"{artist} - {title}",
            "artist": artist,
            "title": title,
            "duration": int(d.get("duration") or 0),
            "lyrics": True,
        })
        if len(items) >= limit:
            break
    return items


def _search(query: str, limit: int) -> list[dict]:
    items: list[dict] = []
    if len(query.split()) >= 4:  # uzun matn — ehtimol qo'shiq so'zlari
        try:
            items += _lyrics_search(query)
        except Exception as e:  # noqa: BLE001
            log.warning("lrclib xatosi: %s", e)
    try:
        items += _yt_search(query, limit)
    except Exception as e:  # noqa: BLE001
        log.warning("YouTube qidiruvi xatosi: %s", e)
        if not items:
            raise
    return items


async def search(query: str, limit: int = 30) -> list[dict]:
    return await asyncio.to_thread(_search, query, limit)


# ---------------- yuklash ----------------
def _download_url(url: str, use_cookies: bool) -> dict:
    make = _yt_opts if use_cookies else _opts
    opts = make(
        format="bestaudio[ext=m4a]/bestaudio/best",
        outtmpl=os.path.join(DOWNLOAD_DIR, "%(extractor)s_%(id)s.%(ext)s"),
        match_filter=match_filter_func(f"duration <= {MAX_DURATION}"),
        postprocessors=[
            # m4a bo'lsa nusxa oladi (sifat yo'qolmaydi), boshqa format bo'lsa m4a ga o'giradi
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"},
        ],
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    downloads = info.get("requested_downloads") or []
    path = downloads[0].get("filepath") if downloads else None
    if not path or not os.path.exists(path):
        raise TooLong()
    if "preview" in str(info.get("format_id", "")):
        os.remove(path)
        raise NotFound("faqat 30 soniyalik parcha")
    return {"path": path, "duration": int(info.get("duration") or 0), "raw": info}


def _soundcloud_fallback(artist: str, title: str, duration: int) -> dict:
    """YouTube ishlamasa — SoundCloud'dan eng mos, to'liq trekni topadi."""
    want = f"{artist} {title}".strip()
    with yt_dlp.YoutubeDL(_opts(extract_flat=True)) as ydl:
        res = ydl.extract_info(f"scsearch12:{want}", download=False)
    candidates = []
    for e in res.get("entries") or []:
        d = int(e.get("duration") or 0)
        if d < 60 or (duration and abs(d - duration) > 25):
            continue
        score = _similar(want, f"{e.get('uploader', '')} {e.get('title', '')}")
        score = max(score, _similar(title, e.get("title", "")))
        if score >= 0.45:
            candidates.append((score, e["url"]))
    for _, url in sorted(candidates, reverse=True)[:5]:
        try:
            return _download_url(url, use_cookies=False)
        except Exception as e:  # noqa: BLE001
            log.info("SoundCloud nomzodi o'tmadi: %s", str(e)[:80])
    raise NotFound("SoundCloud'da mos trek topilmadi")


def _resolve_query(query: str) -> dict:
    found = _yt_search(query, 5)
    if not found:
        raise NotFound(query)
    return found[0]


def _download(item: dict) -> dict:
    if not item.get("url"):
        resolved = _resolve_query(item["query"])
        item = {**item, **{k: resolved[k] for k in ("key", "url")}, "duration": item["duration"] or resolved["duration"]}
    artist, title = item.get("artist", ""), item.get("title", "")
    try:
        res = _download_url(item["url"], use_cookies=True)
        source = "youtube"
    except TooLong:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("YouTube yuklamadi (%s), SoundCloud sinalmoqda", str(e)[:120])
        res = _soundcloud_fallback(artist, title, item.get("duration", 0))
        source = "soundcloud"
    raw = res.pop("raw")
    if not artist:
        artist, title = clean_title(raw.get("title", ""), raw.get("uploader", ""))
    res.update(artist=artist or raw.get("uploader", ""), title=title or raw.get("title", "Audio"),
               key=item.get("key"), source=source)
    return res


async def download(item: dict) -> dict:
    return await asyncio.to_thread(_download, item)


def _video_audio(url: str) -> str:
    """Instagram/TikTok va boshqa havolalardan audio yo'lini olib beradi."""
    opts = _opts(
        format="bestaudio/best",
        outtmpl=os.path.join(DOWNLOAD_DIR, "clip_%(id)s.%(ext)s"),
        match_filter=match_filter_func("duration <= 900"),
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    downloads = info.get("requested_downloads") or []
    path = downloads[0].get("filepath") if downloads else None
    if not path or not os.path.exists(path):
        raise NotFound("video olinmadi")
    return path


async def video_audio(url: str) -> str:
    return await asyncio.to_thread(_video_audio, url)


# ---------------- Shazam ----------------
async def recognize(path: str) -> dict | None:
    """Audio/video fayldagi qo'shiqni aniqlaydi. Topilmasa None."""
    try:
        from shazamio import Shazam
    except ImportError:
        log.warning("shazamio o'rnatilmagan")
        return None
    result = await Shazam().recognize(path)
    track = (result or {}).get("track")
    if not track:
        return None
    return {"artist": track.get("subtitle", ""), "title": track.get("title", "")}


def fmt_duration(sec: int) -> str:
    if not sec:
        return "--:--"
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def safe_filename(artist: str, title: str, ext: str) -> str:
    name = f"{artist} - {title}" if artist else title
    name = re.sub(r'[\\/:*?"<>|]+', "", name).strip()[:90] or "audio"
    return f"{name}{ext}"
