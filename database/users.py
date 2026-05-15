"""database/users.py — All user-related DB operations."""

from __future__ import annotations

import aiosqlite

from database.db import get_db_path


async def get_or_create_user(
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> dict:
    """Upsert a user record and return it."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                updated_at = datetime('now')
            """,
            (user_id, username, first_name),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row)


async def set_user_language(user_id: int, lang_code: str) -> None:
    """Update user language preference ('uz', 'ru', 'en')."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "UPDATE users SET language = ?, updated_at = datetime('now') WHERE user_id = ?",
            (lang_code, user_id),
        )
        await db.commit()


async def get_user_language(user_id: int) -> str:
    """Return user language code, defaulting to 'en'."""
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if (row and row[0]) else "en"


async def is_premium(user_id: int) -> bool:
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute(
            "SELECT is_premium FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def grant_premium(user_id: int) -> bool:
    """Returns True if user existed and was updated."""
    async with aiosqlite.connect(get_db_path()) as db:
        cur = await db.execute(
            "UPDATE users SET is_premium = 1, updated_at = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def revoke_premium(user_id: int) -> bool:
    async with aiosqlite.connect(get_db_path()) as db:
        cur = await db.execute(
            "UPDATE users SET is_premium = 0, updated_at = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ── Transcript helpers ────────────────────────────────────────────────────────

async def save_transcript(
    message_id: int,
    chat_id: int,
    user_id: int,
    text: str,
    language: str | None,
    duration_sec: float | None,
) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO transcripts
                (message_id, chat_id, user_id, text, language, duration_sec)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, chat_id, user_id, text, language, duration_sec),
        )
        await db.commit()


async def get_transcript(message_id: int, chat_id: int) -> dict | None:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transcripts WHERE message_id = ? AND chat_id = ?",
            (message_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ── Usage / Analytics ──────────────────────────────────────────────────────────

async def log_usage(user_id: int, action: str, tokens: int = 0, duration_sec: float = 0.0) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO usage_log (user_id, action, tokens, duration_sec) VALUES (?, ?, ?, ?)",
            (user_id, action, tokens, duration_sec),
        )
        await db.commit()


async def get_analytics(days: int = 1) -> dict:
    """Return total duration and tokens used in the last `days`."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT 
                SUM(duration_sec) as total_duration,
                SUM(tokens) as total_tokens,
                COUNT(*) as total_requests
            FROM usage_log
            WHERE created_at >= date('now', ?)
            """,
            (f"-{days} days",),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {"total_duration": 0, "total_tokens": 0, "total_requests": 0}


async def get_total_users() -> int:
    """Return total number of registered users."""
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def search_user(query: str) -> list[dict]:
    """Search for users by ID or username."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        # Simple LIKE query
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM users WHERE user_id LIKE ? OR username LIKE ? LIMIT 10", 
            (search_term, search_term)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ── Balance Management ────────────────────────────────────────────────────────

async def check_balance(user_id: int, feature: str, requirement: int = 1) -> bool:
    """Return True if user has enough credits for the feature."""
    async with aiosqlite.connect(get_db_path()) as db:
        column = {
            "transcribe": "balance_transcribe_sec",
            "summarize": "balance_summarize_req",
            "translate": "balance_translate_req",
            "actions": "balance_extract_req",
        }.get(feature)
        
        if not column:
            return True
            
        async with db.execute(
            f"SELECT {column} FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            return row[0] >= requirement


async def deduct_balance(user_id: int, feature: str, amount: int = 1) -> None:
    """Subtract credits from user balance."""
    async with aiosqlite.connect(get_db_path()) as db:
        column = {
            "transcribe": "balance_transcribe_sec",
            "summarize": "balance_summarize_req",
            "translate": "balance_translate_req",
            "actions": "balance_extract_req",
        }.get(feature)
        
        if not column:
            return
            
        await db.execute(
            f"UPDATE users SET {column} = MAX(0, {column} - ?), updated_at = datetime('now') WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()


async def add_balance(user_id: int, feature: str, amount: int) -> bool:
    """Add credits to user balance (Admin/Payment use)."""
    async with aiosqlite.connect(get_db_path()) as db:
        column = {
            "transcribe": "balance_transcribe_sec",
            "summarize": "balance_summarize_req",
            "translate": "balance_translate_req",
            "actions": "balance_extract_req",
        }.get(feature)
        
        if not column:
            return False
            
        cur = await db.execute(
            f"UPDATE users SET {column} = {column} + ?, updated_at = datetime('now') WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_user_growth_data(period: str = "daily") -> list[dict]:
    """Returns user join counts grouped by hour, day, month, or year."""
    fmt = {
        "hourly": "%Y-%m-%d %H:00",
        "daily": "%Y-%m-%d",
        "monthly": "%Y-%m",
        "yearly": "%Y",
    }.get(period, "%Y-%m-%d")
    
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT strftime(?, created_at) as label, COUNT(*) as count FROM users GROUP BY label ORDER BY label DESC LIMIT 15",
            (fmt,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in reversed(rows)]


async def get_usage_stats_data(period: str = "daily") -> list[dict]:
    """Returns token usage sums grouped by hour, day, month, or year."""
    fmt = {
        "hourly": "%Y-%m-%d %H:00",
        "daily": "%Y-%m-%d",
        "monthly": "%Y-%m",
        "yearly": "%Y",
    }.get(period, "%Y-%m-%d")
    
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT strftime(?, created_at) as label, SUM(tokens) as total_tokens FROM usage_log GROUP BY label ORDER BY label DESC LIMIT 15",
            (fmt,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in reversed(rows)]
