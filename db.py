"""Baza: PostgreSQL (asyncpg) yoki SQLite (aiosqlite) — bir xil funksiyalar."""
import logging
import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import DATABASE_URL, DB_PATH

log = logging.getLogger(__name__)

_pool = None  # asyncpg pool
_lite = None  # aiosqlite connection

PG_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY, full_name TEXT, username TEXT, joined TEXT,
        active SMALLINT DEFAULT 1, banned SMALLINT DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS channels (
        id SERIAL PRIMARY KEY, chat_id BIGINT UNIQUE, title TEXT, link TEXT)""",
    "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, file_id TEXT)",
    """CREATE TABLE IF NOT EXISTS join_requests (
        chat_id BIGINT, user_id BIGINT, PRIMARY KEY (chat_id, user_id))""",
]
LITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, joined TEXT,
    active INTEGER DEFAULT 1, banned INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE, title TEXT, link TEXT);
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, file_id TEXT);
CREATE TABLE IF NOT EXISTS join_requests (
    chat_id INTEGER, user_id INTEGER, PRIMARY KEY (chat_id, user_id));
"""


def _clean_pg_url(url: str) -> str:
    # asyncpg "channel_binding" parametrini tushunmaydi (Neon linkida bo'ladi)
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "channel_binding"]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _to_pg(sql: str) -> str:
    n = 0

    def repl(_):
        nonlocal n
        n += 1
        return f"${n}"

    return re.sub(r"\?", repl, sql)


async def init():
    global _pool, _lite
    if DATABASE_URL:
        import asyncpg

        _pool = await asyncpg.create_pool(
            _clean_pg_url(DATABASE_URL),
            min_size=1,
            max_size=5,
            statement_cache_size=0,  # Neon pooler (pgbouncer) uchun
            max_inactive_connection_lifetime=60,
        )
        async with _pool.acquire() as con:
            for stmt in PG_SCHEMA:
                await con.execute(stmt)
        log.info("Baza: PostgreSQL")
    else:
        import aiosqlite

        _lite = await aiosqlite.connect(DB_PATH)
        _lite.row_factory = aiosqlite.Row
        await _lite.executescript(LITE_SCHEMA)
        await _lite.commit()
        log.info("Baza: SQLite (%s)", DB_PATH)


async def close():
    if _pool:
        await _pool.close()
    if _lite:
        await _lite.close()


async def _run(kind: str, sql: str, *args):
    if _pool:
        for attempt in (1, 2):  # Neon uxlab qolsa ulanish uzilishi mumkin — bir marta qayta urinamiz
            try:
                async with _pool.acquire() as con:
                    if kind == "exec":
                        return await con.execute(_to_pg(sql), *args)
                    rows = await con.fetch(_to_pg(sql), *args)
                    return [dict(r) for r in rows]
            except Exception as e:  # noqa: BLE001
                if attempt == 2 or "connection" not in str(e).lower():
                    raise
                log.warning("DB ulanishi uzildi, qayta urinilmoqda: %s", e)
    cur = await _lite.execute(sql, args)
    if kind == "exec":
        await _lite.commit()
        return None
    return [dict(r) for r in await cur.fetchall()]


async def _exec(sql, *args):
    await _run("exec", sql, *args)


async def _fetch(sql, *args) -> list[dict]:
    return await _run("fetch", sql, *args)


async def _val(sql, *args):
    rows = await _fetch(sql, *args)
    return next(iter(rows[0].values())) if rows else None


# ---------------- foydalanuvchilar ----------------
async def add_user(user_id: int, full_name: str, username: str | None):
    await _exec(
        "INSERT INTO users (id, full_name, username, joined) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (id) DO UPDATE SET full_name = excluded.full_name, "
        "username = excluded.username, active = 1",
        user_id, full_name, username, date.today().isoformat(),
    )


async def delete_user(user_id: int):
    await _exec("DELETE FROM users WHERE id = ?", user_id)
    await _exec("DELETE FROM join_requests WHERE user_id = ?", user_id)


async def all_user_ids() -> list[int]:
    return [r["id"] for r in await _fetch("SELECT id FROM users WHERE active = 1 AND banned = 0")]


async def all_users() -> list[dict]:
    return await _fetch("SELECT * FROM users ORDER BY joined")


async def set_inactive(user_id: int):
    await _exec("UPDATE users SET active = 0 WHERE id = ?", user_id)


async def banned_ids() -> set[int]:
    return {r["id"] for r in await _fetch("SELECT id FROM users WHERE banned = 1")}


async def set_banned(user_id: int, banned: bool) -> bool:
    """True qaytaradi, agar foydalanuvchi bazada bo'lsa."""
    exists = await _val("SELECT COUNT(*) FROM users WHERE id = ?", user_id)
    if not exists:
        return False
    await _exec("UPDATE users SET banned = ? WHERE id = ?", 1 if banned else 0, user_id)
    return True


async def stats() -> dict:
    return {
        "total": await _val("SELECT COUNT(*) FROM users"),
        "active": await _val("SELECT COUNT(*) FROM users WHERE active = 1"),
        "banned": await _val("SELECT COUNT(*) FROM users WHERE banned = 1"),
        "today": await _val("SELECT COUNT(*) FROM users WHERE joined = ?", date.today().isoformat()),
        "songs": await _val("SELECT COUNT(*) FROM cache"),
    }


# ---------------- majburiy obuna kanallari ----------------
async def add_channel(chat_id: int, title: str, link: str):
    await _exec(
        "INSERT INTO channels (chat_id, title, link) VALUES (?, ?, ?) "
        "ON CONFLICT (chat_id) DO UPDATE SET title = excluded.title, link = excluded.link",
        chat_id, title, link,
    )


async def get_channels() -> list[dict]:
    return await _fetch("SELECT * FROM channels ORDER BY id")


async def delete_channel(row_id: int):
    await _exec("DELETE FROM channels WHERE id = ?", row_id)


async def add_join_request(chat_id: int, user_id: int):
    await _exec(
        "INSERT INTO join_requests (chat_id, user_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
        chat_id, user_id,
    )


async def has_join_request(chat_id: int, user_id: int) -> bool:
    return bool(await _val(
        "SELECT COUNT(*) FROM join_requests WHERE chat_id = ? AND user_id = ?", chat_id, user_id
    ))


# ---------------- yuklangan qo'shiqlar keshi ----------------
async def get_cached(key: str) -> str | None:
    return await _val("SELECT file_id FROM cache WHERE key = ?", key)


async def set_cached(key: str, file_id: str):
    await _exec(
        "INSERT INTO cache (key, file_id) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET file_id = excluded.file_id",
        key, file_id,
    )
