"""Vaqtinchalik: serverda qaysi manba ishlashini tekshirish (/diag)."""
import asyncio
import os
import tempfile
import time

import yt_dlp


def _try(name, fn):
    t = time.time()
    try:
        return f"OK   {name} ({time.time() - t:.1f}s): {fn()}"
    except Exception as e:  # noqa: BLE001
        return f"FAIL {name} ({time.time() - t:.1f}s): {str(e).replace(chr(10), ' ')[:200]}"


def _sc_many():
    out = []
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as y:
        r = y.extract_info("scsearch10:Shahzoda Ayt", download=False)
    for e in r["entries"]:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "format": "bestaudio/best"}) as y:
                i = y.extract_info(e["url"], download=False)
            out.append(f"ok:{i.get('format_id')}:{i.get('duration')}")
        except Exception as ex:  # noqa: BLE001
            out.append("drm" if "DRM" in str(ex) else "err")
    return " ".join(out)


def _sc_file():
    d = tempfile.mkdtemp()
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as y:
        r = y.extract_info("scsearch10:Konsta", download=False)
    for e in r["entries"]:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio/best", "outtmpl": f"{d}/%(id)s.%(ext)s"}) as y:
                i = y.extract_info(e["url"], download=True)
            p = i["requested_downloads"][0]["filepath"]
            return p
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("hech biri yuklanmadi")


def _video(url):
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as y:
        i = y.extract_info(url, download=False)
    return f"{i.get('title', '')[:50]} {i.get('duration')}s"


def _shazam(path):
    from shazamio import Shazam

    async def go():
        r = await Shazam().recognize(path)
        t = r.get("track") or {}
        return f"{t.get('subtitle')} - {t.get('title')}"

    return asyncio.run(go())


def run() -> str:
    lines = [f"yt-dlp {yt_dlp.version.__version__}"]
    lines.append(_try("soundcloud:10ta", _sc_many))
    holder = {}
    lines.append(_try("soundcloud:file", lambda: holder.setdefault("p", _sc_file())))
    if holder.get("p"):
        lines.append(_try("shazam", lambda: _shazam(holder["p"])))
    lines.append(_try("instagram", lambda: _video("https://www.instagram.com/p/aye83DjauH/")))
    lines.append(_try("instagram-reel", lambda: _video("https://www.instagram.com/reel/CWqAgUZgCku/")))
    lines.append(_try("tiktok", lambda: _video("https://www.tiktok.com/@scout2015/video/6718335390845095173")))
    lines.append(_try("lrclib", lambda: __import__("urllib.request").request.urlopen("https://lrclib.net/api/search?q=seni%20sevaman", timeout=15).status))
    return "\n".join(lines)
