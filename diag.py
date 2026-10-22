"""Vaqtinchalik: serverda qaysi manba ishlashini tekshirish (/diag)."""
import asyncio
import json
import tempfile
import time
import urllib.request

import yt_dlp

VID = "IMdfvJ6Q2Cg"
UA = {"User-Agent": "Mozilla/5.0"}


def _try(name, fn):
    t = time.time()
    try:
        return f"OK   {name} ({time.time() - t:.1f}s): {fn()}"
    except Exception as e:  # noqa: BLE001
        return f"FAIL {name} ({time.time() - t:.1f}s): {str(e).replace(chr(10), ' ')[:150]}"


def _get(url, n=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read(n) if n else r.read()


def _invidious(host):
    d = json.loads(_get(f"https://{host}/api/v1/videos/{VID}?local=true"))
    fmts = [f for f in d.get("adaptiveFormats", []) if f.get("type", "").startswith("audio")]
    url = fmts[-1]["url"]
    if url.startswith("/"):
        url = f"https://{host}{url}"
    return f"{len(fmts)} audio, yuklandi {len(_get(url, 200000))} bayt"


def _piped(host):
    d = json.loads(_get(f"https://{host}/streams/{VID}"))
    s = d["audioStreams"]
    return f"{len(s)} audio, yuklandi {len(_get(s[0]['url'], 200000))} bayt"


def _shazam():
    from shazamio import Shazam

    d = tempfile.mkdtemp()
    with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio/best", "outtmpl": f"{d}/a.%(ext)s"}) as y:
        i = y.extract_info("https://www.tiktok.com/@scout2015/video/6718335390845095173", download=True)
    path = i["requested_downloads"][0]["filepath"]

    async def go():
        r = await Shazam().recognize(path)
        t = r.get("track") or {}
        return f"{t.get('subtitle')} - {t.get('title')} | keys={list(r)[:5]}"

    return asyncio.run(go())


def run() -> str:
    lines = []
    for h in ["inv.nadeko.net", "yewtu.be", "invidious.nerdvpn.de", "inv.tux.pizza", "invidious.f5.si", "iv.melmac.space"]:
        lines.append(_try(f"invidious:{h}", lambda h=h: _invidious(h)))
    for h in ["pipedapi.kavin.rocks", "pipedapi.adminforge.de", "api.piped.private.coffee"]:
        lines.append(_try(f"piped:{h}", lambda h=h: _piped(h)))
    lines.append(_try("shazam(tiktok)", _shazam))
    return "\n".join(lines)
