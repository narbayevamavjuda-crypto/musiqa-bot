"""Vaqtinchalik: serverda qaysi manba ishlashini tekshirish (/diag)."""
import time
import traceback

import yt_dlp

VIDEO = "https://www.youtube.com/watch?v=IMdfvJ6Q2Cg"
CLIENTS = ["default", "tv_embedded", "web_embedded", "mweb", "android_vr", "ios", "tv", "web_safari", "android"]


def _try(name, fn):
    t = time.time()
    try:
        res = fn()
        return f"OK   {name} ({time.time() - t:.1f}s): {res}"
    except Exception as e:  # noqa: BLE001
        msg = str(e).replace("\n", " ")[:160]
        return f"FAIL {name} ({time.time() - t:.1f}s): {msg}"


def _yt(client):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "format": "bestaudio/best"}
    if client != "default":
        opts["extractor_args"] = {"youtube": {"player_client": [client]}}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(VIDEO, download=False)
    return f"{info.get('format_id')} {info.get('abr')}kbps"


def _sc_search():
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as y:
        r = y.extract_info("scsearch5:Shahzoda Ayt", download=False)
    return " | ".join(f"{e.get('title')} [{int(e.get('duration') or 0)}s]" for e in r["entries"])


def _sc_dl():
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as y:
        r = y.extract_info("scsearch1:Shahzoda", download=False)
    url = r["entries"][0]["url"]
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "format": "bestaudio/best"}) as y:
        info = y.extract_info(url, download=False)
    return f"{info.get('title')} {info.get('format_id')} {info.get('duration')}s"


def run() -> str:
    lines = [f"yt-dlp {yt_dlp.version.__version__}"]
    for c in CLIENTS:
        lines.append(_try(f"youtube:{c}", lambda c=c: _yt(c)))
    lines.append(_try("soundcloud:search", _sc_search))
    lines.append(_try("soundcloud:stream", _sc_dl))
    return "\n".join(lines)
