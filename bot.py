"""
bot.py — VoiceScribe AI Telegram Bot entry point.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    MessageHandler,
)

from config import config
from database.db import init_db
from database.users import get_setting, reset_all_monthly_balances, set_setting
from handlers.callbacks import (
    callback_actions,
    callback_back_to_main,
    callback_check_sub,
    callback_copy_actions,
    callback_locked,
    callback_noop,
    callback_set_lang,
    callback_summarize,
    callback_translate_exec,
    callback_translate_menu,
    callback_buy_menu,
    callback_buy_plan,
    callback_admin_chart,
    callback_tts,
    callback_tts_lang,
    callback_tts_select,
    callback_tts_preview,
)
from handlers.commands import (
    cmd_help,
    cmd_start,
    cmd_buy,
    cmd_analytics,
    cmd_users,
    cmd_user,
    cmd_set_balance,
    cmd_db_dump,
    cmd_tts,
    cmd_image,
)
from handlers.voice import handle_voice
from handlers.text import handle_text
from handlers.photo import handle_photo

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def _monthly_reset_loop() -> None:
    """Background task: reset all user balances to defaults on the 1st of each month."""
    while True:
        now = datetime.utcnow()
        current_month = now.strftime("%Y-%m")

        if now.day == 1:
            last_reset = await get_setting("last_monthly_reset")
            if last_reset != current_month:
                count = await reset_all_monthly_balances()
                await set_setting("last_monthly_reset", current_month)
                logger.info("Monthly balance reset complete — %d users reset for %s.", count, current_month)

        # Sleep until the start of the next day (UTC midnight + 1 min)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        await asyncio.sleep((tomorrow - now).total_seconds())


async def post_init(application: Application) -> None:
    logger.info("Initialising database…")
    await init_db()
    logger.info("Database ready.")
    asyncio.create_task(_monthly_reset_loop())

    # ── One-time: image generation & editing launch + announcement (runs once, ever) ──
    from announce_image_feature import run_image_announcement
    asyncio.create_task(run_image_announcement(application))

    # ── Verify required channel access ───────────────────────
    try:
        chat = await application.bot.get_chat(config.required_channel)
        logger.info("✅ Required channel found: %s (%s)", chat.title, chat.id)
    except Exception as e:
        logger.error("❌ CRITICAL: Could not access required channel %s: %s", config.required_channel, e)
        logger.error("👉 FIX: Add the bot to the channel as an ADMINISTRATOR.")

    await application.bot.set_my_commands([
        BotCommand("start",  "🏠 Welcome screen & instructions"),
        BotCommand("help",   "📖 How to use the bot"),
        BotCommand("status", "👤 Check your plan & language"),
        BotCommand("tts",    "🔊 Convert text to speech"),
        BotCommand("image",  "🎨 Generate an image from text"),
    ])
    
    # Show admin commands ONLY to admins in their menu
    from telegram import BotCommandScopeChat
    admin_commands = [
        BotCommand("start",     "🏠 Welcome screen & instructions"),
        BotCommand("help",      "📖 How to use the bot"),
        BotCommand("buy",       "💳 Balance & Buy Credits"),
        BotCommand("tts",       "🔊 Convert text to speech"),
        BotCommand("image",     "🎨 Generate an image from text"),
        BotCommand("analytics", "📊 [Admin] View usage statistics"),
        BotCommand("users",     "👥 [Admin] View total users"),
        BotCommand("user",      "🔍 [Admin] Search for a user"),
        BotCommand("set_balance", "💰 [Admin] Adjust user balance"),
        BotCommand("db_dump",   "📦 [Admin] Download database dump"),
    ]
    for admin_id in config.admin_ids:
        try:
            await application.bot.set_my_commands(
                admin_commands, 
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except Exception as e:
            logger.warning("Could not set admin commands for %s: %s", admin_id, e)

    logger.info("Bot commands registered.")


def build_app() -> Application:
    app = (
        ApplicationBuilder()
        .token(config.bot_token)
        .post_init(post_init)
        .build()
    )

    # ── Commands ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("buy",    cmd_buy))
    app.add_handler(CommandHandler("status", cmd_buy))
    app.add_handler(CommandHandler("tts",    cmd_tts))
    app.add_handler(CommandHandler("image",  cmd_image))
    app.add_handler(CommandHandler("set_balance", cmd_set_balance))
    app.add_handler(CommandHandler("analytics", cmd_analytics))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("user", cmd_user))
    app.add_handler(CommandHandler("db_dump", cmd_db_dump))

    # ── Audio & Direct Text (TTS) ─────────────────────────────────────────────
    audio_filter = filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE | filters.VIDEO
    app.add_handler(MessageHandler(audio_filter, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
 
    # ── Callbacks ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_set_lang,    pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(callback_summarize,   pattern=r"^summarize:"))
    app.add_handler(CallbackQueryHandler(callback_actions,     pattern=r"^actions:"))
    app.add_handler(CallbackQueryHandler(callback_translate_menu, pattern=r"^trans_menu:"))
    app.add_handler(CallbackQueryHandler(callback_translate_exec, pattern=r"^trans:"))
    app.add_handler(CallbackQueryHandler(callback_tts,           pattern=r"^tts:"))
    app.add_handler(CallbackQueryHandler(callback_tts_lang,      pattern=r"^tts_lang:"))
    app.add_handler(CallbackQueryHandler(callback_tts_select,    pattern=r"^tts_sel:"))
    app.add_handler(CallbackQueryHandler(callback_tts_preview,   pattern=r"^tts_prev:"))
    app.add_handler(CallbackQueryHandler(callback_back_to_main, pattern=r"^back:"))
    app.add_handler(CallbackQueryHandler(callback_copy_actions, pattern=r"^copy:"))
    app.add_handler(CallbackQueryHandler(callback_check_sub,    pattern=r"^check_sub$"))
    app.add_handler(CallbackQueryHandler(callback_buy_menu,     pattern=r"^buy_menu:"))
    app.add_handler(CallbackQueryHandler(callback_buy_plan,     pattern=r"^buy:"))
    app.add_handler(CallbackQueryHandler(callback_admin_chart,  pattern=r"^chart:"))
    app.add_handler(CallbackQueryHandler(callback_locked,      pattern=r"^locked:"))
    app.add_handler(CallbackQueryHandler(callback_noop,        pattern=r"^noop$"))

    return app


def main() -> None:
    logger.info("=" * 60)
    logger.info("  VoiceScribe AI Bot — Starting up")
    logger.info("=" * 60)
    logger.info("Admin IDs: %s", config.admin_ids)
    logger.info("Gemini:    %s", config.gemini_model)
    logger.info("Image:     %s", config.image_model)
    logger.info("=" * 60)

    app = build_app()
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
