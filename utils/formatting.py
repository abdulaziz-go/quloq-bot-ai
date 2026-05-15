"""utils/formatting.py — Rich Telegram message formatters."""

from __future__ import annotations

import math

from services.action_detector import ActionItems

# ── Emoji constants ───────────────────────────────────────────────────────────
DIVIDER = "─" * 32


def _duration_str(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _language_flag(lang: str | None) -> str:
    """Return a best-effort language label."""
    if not lang:
        return "Auto-detected"
    return lang.capitalize()


# ── Transcript ────────────────────────────────────────────────────────────────

def format_transcript(
    text: str,
    language: str | None,
    duration_sec: float | None,
    is_forwarded: bool = False,
) -> str:
    header = "📨 Forwarded Voice — Transcript" if is_forwarded else "🎙️ Voice Transcript"
    lang = _language_flag(language)
    dur = _duration_str(duration_sec)

    return (
        f"*{_escape(header)}*\n"
        f"`{DIVIDER}`\n"
        f"{_escape(text)}\n"
        f"`{DIVIDER}`\n"
        f"🌐 *Language:* {_escape(lang)}   ⏱ *Duration:* {_escape(dur)}"
    )


# ── Summary ───────────────────────────────────────────────────────────────────

def format_summary(summary: str) -> str:
    return (
        f"💡 *AI Summary*\n"
        f"`{DIVIDER}`\n"
        f"{_escape(summary)}"
    )


# ── Action Items ──────────────────────────────────────────────────────────────

def format_actions(actions: ActionItems) -> str:
    if actions.is_empty:
        return (
            "✅ *Smart Action Detection*\n"
            "`────────────────────────────────`\n"
            "No tasks, deadlines or questions were detected in this message\\."
        )

    lines = ["✅ *Smart Action Detection*", f"`{DIVIDER}`"]

    if actions.tasks:
        lines.append("\n📌 *Tasks*")
        for t in actions.tasks:
            lines.append(f"  ◻️ {_escape(t)}")

    if actions.deadlines:
        lines.append("\n⏰ *Deadlines*")
        for d in actions.deadlines:
            lines.append(f"  🗓 {_escape(d)}")

    if actions.questions:
        lines.append("\n❓ *Questions*")
        for q in actions.questions:
            lines.append(f"  💬 {_escape(q)}")

    lines.append(f"\n`{DIVIDER}`")
    lines.append(f"_{actions.total_count} item\\(s\\) extracted_")
    return "\n".join(lines)


def format_action_copy_text(actions: ActionItems) -> str:
    """Plain-text version suitable for copying."""
    parts: list[str] = []
    if actions.tasks:
        parts.append("TASKS\n" + "\n".join(f"☐ {t}" for t in actions.tasks))
    if actions.deadlines:
        parts.append("DEADLINES\n" + "\n".join(f"🗓 {d}" for d in actions.deadlines))
    if actions.questions:
        parts.append("QUESTIONS\n" + "\n".join(f"? {q}" for q in actions.questions))
    return "\n\n".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    # List of all characters that MUST be escaped in MarkdownV2
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


# ── Premium locked message ────────────────────────────────────────────────────

def format_premium_locked(feature: str) -> str:
    return (
        f"🔒 *{_escape(feature)} — Premium Feature*\n\n"
        "This feature is available to premium users\\.\n"
        "Ask the bot admin to grant you premium access, or use /status to check your plan\\."
    )


# Supported formats: OGG, MP3, M4A, WAV, FLAC, MP4

