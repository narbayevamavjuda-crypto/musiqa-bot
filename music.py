"""Qo'shiq qidirish va yuklash (YouTube, zaxira — SoundCloud)."""
import asyncio
import logging
import os
import re
import shutil
import tempfile

import yt_dlp
from yt_dlp.utils import match_filter_func

from config import COOKIES_FILE, DOWNLOAD_DIR, MAX_DURATION

log = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YT_LINK = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/)|youtu\.be/|music\.youtube\.com/watch\?v=)([\w-]{11})")

# /etc/secrets faqat o'qish uchun, yt-dlp esa cookies faylini yangilaydi — nusxasini olamiz
_cookies = ""
if COOKIES_FILE:
    _cookies = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    shutil.copy(COOKIES_FILE, _cookies)


def _base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True}
    if _cookies:
        opts["cookiefile"] = _cookies
    return opts


def _flat_search(prefix: str, query: str, limit: int, src: str) -> list[dict]:
    opts = _base_opts() | {"extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"{prefix}{limit}:{query}", download=False)
    items = []
    for e in info.get("entries") or []:
        if not e or not e.get("id"):
            continue
        duration = int(e.get("duration") or 0)
        if duration and duration > MAX_DURATION:
            continue
        url = e.get("url") or e.get("webpage_url")
        if src == "yt":
            url = f"https://www.youtube.com/watch?v={e['id']}"
        items.append({
            "key": f"{src}:{e['id']}",
            "url": url,
            "title": e.get("title") or "Nomsiz",
            "duration": duration,
        })
    return items


def _search(query: str, limit: int) -> list[dict]:
    try:
        items = _flat_search("ytsearch", query, limit, "yt")
        if items:
            return items
    except Exception as e:  # noqa: BLE001
        log.warning("YouTube qidiruvi ishlamadi, SoundCloud'ga o'tilmoqda: %s", e)
    return _flat_search("scsearch", query, limit, "sc")


def _download(url: str) -> dict:
    opts = _base_opts() | {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(extractor)s_%(id)s.%(ext)s"),
        "match_filter": match_filter_func(f"duration <= {MAX_DURATION}"),
        "postprocessors": [
            # m4a bo'lsa shunchaki nusxa oladi, boshqa format bo'lsa m4a (AAC) ga o'giradi
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "128"},
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    downloads = info.get("requested_downloads") or []
    path = downloads[0].get("filepath") if downloads else None
    if not path or not os.path.exists(path):
        raise TooLong()
    return {
        "path": path,
        "title": info.get("track") or info.get("title") or "Audio",
        "performer": info.get("artist") or info.get("creator") or info.get("channel") or info.get("uploader") or "",
        "duration": int(info.get("duration") or 0),
    }


class TooLong(Exception):
    pass


async def search(query: str, limit: int = 30) -> list[dict]:
    return await asyncio.to_thread(_search, query, limit)


async def download(url: str) -> dict:
    return await asyncio.to_thread(_download, url)


def fmt_duration(sec: int) -> str:
    if not sec:
        return "--:--"
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
