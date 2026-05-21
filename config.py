"""
config.py — Centralised configuration loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {key}\n"
            f"Copy .env.example → .env and fill in the values."
        )
    return value


def _int_list(key: str, default: str = "") -> list[int]:
    raw = os.getenv(key, default)
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


@dataclass(frozen=True)
class Config:
    # ── Telegram ──────────────────────────────────────────────
    bot_token: str

    # ── Google AI ────────────────────────────────────────────
    google_api_key: str

    # ── Admin ────────────────────────────────────────────────
    admin_ids: list[int]

    # ── Paths ────────────────────────────────────────────────
    database_path: Path

    # ── Gemini Models ─────────────────────────────────────────
    # Using the best models available for your account
    gemini_model: str = "gemini-2.5-flash"
    audio_model: str  = "gemini-2.5-flash"

    # ── Limits ───────────────────────────────────────────────
    max_audio_size_mb: int = 20

    # ── Summary ──────────────────────────────────────────────
    summary_max_sentences: int = 5

    # ── Channel Subscription ─────────────────────────────────
    required_channel: str = "@QuloqBotAI"


def load_config() -> Config:
    db_path = Path(os.getenv("DATABASE_PATH", "data/bot.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=_require("TELEGRAM_BOT_TOKEN"),
        google_api_key=_require("GOOGLE_API_KEY"),
        admin_ids=_int_list("ADMIN_IDS"),
        required_channel=os.getenv("REQUIRED_CHANNEL", "@QuloqBotAI"),
        database_path=db_path,
    )


# Singleton — import this everywhere
config = load_config()
