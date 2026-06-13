"""database/db.py — SQLite initialisation and connection helper."""

from __future__ import annotations

import aiosqlite

from config import config

_DB_PATH = str(config.database_path)


CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    language    TEXT DEFAULT 'en',
    is_premium  INTEGER NOT NULL DEFAULT 0,
    balance_transcribe_sec INTEGER DEFAULT 5400,
    balance_summarize_req  INTEGER DEFAULT 30,
    balance_translate_req  INTEGER DEFAULT 30,
    balance_extract_req    INTEGER DEFAULT 30,
    balance_tts_req        INTEGER DEFAULT 150,
    balance_image_req      INTEGER DEFAULT 30,
    referrer    TEXT DEFAULT '(direct)',
    referral_credited INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_TRANSCRIPTS = """
CREATE TABLE IF NOT EXISTS transcripts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   INTEGER NOT NULL,
    chat_id      INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    text         TEXT    NOT NULL,
    language     TEXT,
    duration_sec REAL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(message_id, chat_id)
);
"""

CREATE_USAGE_LOG = """
CREATE TABLE IF NOT EXISTS usage_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    action       TEXT    NOT NULL,   -- 'transcribe' | 'summarize' | 'actions' | 'translate'
    tokens       INTEGER DEFAULT 0,
    duration_sec REAL    DEFAULT 0.0,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_PURCHASES = """
CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    feature      TEXT    NOT NULL,
    amount       INTEGER NOT NULL,
    revenue_uzs  INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_BOT_SETTINGS = """
CREATE TABLE IF NOT EXISTS bot_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


async def init_db() -> None:
    """Create all tables and run migrations."""
    async with aiosqlite.connect(_DB_PATH) as db:
        # Create tables
        await db.execute(CREATE_USERS)
        await db.execute(CREATE_TRANSCRIPTS)
        await db.execute(CREATE_USAGE_LOG)
        await db.execute(CREATE_PURCHASES)
        await db.execute(CREATE_BOT_SETTINGS)
        
        # Migration: Add 'language' column if it doesn't exist
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
        except aiosqlite.OperationalError:
            pass  # Column already exists

        # Migration: Add 'referrer' column if it doesn't exist
        try:
            await db.execute("ALTER TABLE users ADD COLUMN referrer TEXT DEFAULT '(direct)'")
        except aiosqlite.OperationalError:
            pass

        # Migration: Add balance columns for existing users
        balance_cols = [
            ("balance_transcribe_sec", "INTEGER DEFAULT 5400"),
            ("balance_summarize_req", "INTEGER DEFAULT 30"),
            ("balance_translate_req", "INTEGER DEFAULT 30"),
            ("balance_extract_req", "INTEGER DEFAULT 30"),
            ("balance_tts_req", "INTEGER DEFAULT 150"),
            ("balance_image_req", "INTEGER DEFAULT 30"),
            ("referral_credited", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col_name, col_def in balance_cols:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            except aiosqlite.OperationalError:
                pass
            
        # Migration: Add usage tracking columns
        try:
            await db.execute("ALTER TABLE usage_log ADD COLUMN tokens INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
            
        try:
            await db.execute("ALTER TABLE usage_log ADD COLUMN duration_sec REAL DEFAULT 0.0")
        except aiosqlite.OperationalError:
            pass

        try:
            await db.execute("ALTER TABLE usage_log ADD COLUMN input_tokens INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass

        try:
            await db.execute("ALTER TABLE usage_log ADD COLUMN output_tokens INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
            
        await db.commit()


def get_db_path() -> str:
    return _DB_PATH
