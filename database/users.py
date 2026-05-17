"""database/users.py — All user-related DB operations."""

from __future__ import annotations

import aiosqlite

from database.db import get_db_path


async def get_or_create_user(
    user_id: int,
    username: str | None,
    first_name: str | None,
    referrer: str = '(direct)',
) -> dict:
    """Upsert a user record and return it, preserving first referrer."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, referrer)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                updated_at = datetime('now')
            """,
            (user_id, username, first_name, referrer),
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

async def log_usage(
    user_id: int, 
    action: str, 
    tokens: int = 0, 
    duration_sec: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0
) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO usage_log 
            (user_id, action, tokens, duration_sec, input_tokens, output_tokens) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, action, tokens, duration_sec, input_tokens, output_tokens),
        )
        await db.commit()


async def log_purchase(user_id: int, feature: str, amount: int, revenue_uzs: int) -> None:
    """Log a purchase transaction in the purchases table."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO purchases (user_id, feature, amount, revenue_uzs) VALUES (?, ?, ?, ?)",
            (user_id, feature, amount, revenue_uzs),
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
            "tts": "balance_tts_req",
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
            "tts": "balance_tts_req",
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
            "tts": "balance_tts_req",
        }.get(feature)
        
        if not column:
            return False
            
        cur = await db.execute(
            f"UPDATE users SET {column} = {column} + ?, updated_at = datetime('now') WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def reset_all_monthly_balances() -> int:
    """Reset every user's balance columns to monthly defaults. Returns number of rows updated."""
    async with aiosqlite.connect(get_db_path()) as db:
        cur = await db.execute(
            """
            UPDATE users SET
                balance_transcribe_sec = 3600,
                balance_summarize_req  = 20,
                balance_translate_req  = 20,
                balance_extract_req    = 20,
                balance_tts_req        = 100,
                updated_at             = datetime('now')
            """
        )
        await db.commit()
        return cur.rowcount


async def get_setting(key: str) -> str | None:
    """Read a value from bot_settings table."""
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    """Upsert a value in bot_settings table."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_user_growth_data(period: str = "daily") -> list[dict]:
    """Returns user join counts grouped by hour, day, month, or year (converted to Uzbekistan Time +5 hours)."""
    fmt = {
        "hourly": "%Y-%m-%d %H:00",
        "daily": "%Y-%m-%d",
        "monthly": "%Y-%m",
        "yearly": "%Y",
    }.get(period, "%Y-%m-%d")
    
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT strftime(?, created_at, '+5 hours') as label, COUNT(*) as count FROM users GROUP BY label ORDER BY label DESC LIMIT 15",
            (fmt,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in reversed(rows)]


async def get_usage_stats_data(period: str = "daily") -> list[dict]:
    """Returns token usage sums grouped by hour, day, month, or year (converted to Uzbekistan Time +5 hours)."""
    fmt = {
        "hourly": "%Y-%m-%d %H:00",
        "daily": "%Y-%m-%d",
        "monthly": "%Y-%m",
        "yearly": "%Y",
    }.get(period, "%Y-%m-%d")
    
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT strftime(?, created_at, '+5 hours') as label, SUM(tokens) as total_tokens FROM usage_log GROUP BY label ORDER BY label DESC LIMIT 15",
            (fmt,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in reversed(rows)]


async def get_daily_summary() -> dict:
    """Collects comprehensive daily analytics for Uzbekistan Time (UTC+5)."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. New Users
        async with db.execute(
            "SELECT COUNT(*) as count FROM users WHERE date(created_at, '+5 hours') = date('now', '+5 hours')"
        ) as cur:
            row = await cur.fetchone()
            new_users = row["count"] if row else 0

        # 2. Referrers
        async with db.execute(
            """
            SELECT referrer, COUNT(*) as count 
            FROM users 
            WHERE date(created_at, '+5 hours') = date('now', '+5 hours') 
            GROUP BY referrer 
            ORDER BY count DESC
            """
        ) as cur:
            rows = await cur.fetchall()
            referrers = [dict(r) for r in rows]

        # 3. Total Transcriptions
        async with db.execute(
            "SELECT COUNT(*) as count FROM usage_log WHERE action = 'transcribe' AND date(created_at, '+5 hours') = date('now', '+5 hours')"
        ) as cur:
            row = await cur.fetchone()
            total_transcriptions = row["count"] if row else 0

        # 4. Total Audio Length
        async with db.execute(
            "SELECT SUM(duration_sec) as total_sec FROM usage_log WHERE action = 'transcribe' AND date(created_at, '+5 hours') = date('now', '+5 hours')"
        ) as cur:
            row = await cur.fetchone()
            total_audio_sec = row["total_sec"] if (row and row["total_sec"]) else 0.0

        # 5. Daily Active Users (DAU)
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) as count FROM usage_log WHERE date(created_at, '+5 hours') = date('now', '+5 hours')"
        ) as cur:
            row = await cur.fetchone()
            dau = row["count"] if row else 0

        # 6. Total Users
        async with db.execute("SELECT COUNT(*) as count FROM users") as cur:
            row = await cur.fetchone()
            total_users = row["count"] if row else 0

        # 7. AI Token Usage
        async with db.execute(
            """
            SELECT 
                SUM(CASE WHEN action != 'tts' THEN (CASE WHEN input_tokens > 0 THEN input_tokens ELSE CAST(tokens * 0.8 AS INTEGER) END) ELSE 0 END) as input_t,
                SUM(CASE WHEN action != 'tts' THEN (CASE WHEN output_tokens > 0 THEN output_tokens ELSE CAST(tokens * 0.2 AS INTEGER) END) ELSE 0 END) as output_t
            FROM usage_log
            WHERE date(created_at, '+5 hours') = date('now', '+5 hours')
            """
        ) as cur:
            row = await cur.fetchone()
            input_tokens = row["input_t"] if (row and row["input_t"]) else 0
            output_tokens = row["output_t"] if (row and row["output_t"]) else 0

        # 8. TTS Usage
        async with db.execute(
            """
            SELECT 
                COUNT(*) as gens,
                SUM(tokens) as chars
            FROM usage_log
            WHERE action = 'tts' AND date(created_at, '+5 hours') = date('now', '+5 hours')
            """
        ) as cur:
            row = await cur.fetchone()
            tts_gens = row["gens"] if (row and row["gens"]) else 0
            tts_chars = row["chars"] if (row and row["chars"]) else 0

        # 9. Purchases
        async with db.execute(
            """
            SELECT 
                COUNT(*) as count,
                SUM(revenue_uzs) as revenue
            FROM purchases
            WHERE date(created_at, '+5 hours') = date('now', '+5 hours')
            """
        ) as cur:
            row = await cur.fetchone()
            purchase_count = row["count"] if (row and row["count"]) else 0
            revenue_uzs = row["revenue"] if (row and row["revenue"]) else 0

        # 10. Credits Sold details
        async with db.execute(
            """
            SELECT feature, SUM(amount) as amount
            FROM purchases
            WHERE date(created_at, '+5 hours') = date('now', '+5 hours')
            GROUP BY feature
            """
        ) as cur:
            rows = await cur.fetchall()
            credits_sold = [dict(r) for r in rows]

        return {
            "new_users": new_users,
            "referrers": referrers,
            "total_transcriptions": total_transcriptions,
            "total_audio_sec": total_audio_sec,
            "dau": dau,
            "total_users": total_users,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tts_gens": tts_gens,
            "tts_chars": tts_chars,
            "purchase_count": purchase_count,
            "revenue_uzs": revenue_uzs,
            "credits_sold": credits_sold,
        }
