"""handlers/text.py — Handle direct text messages for Text-to-Speech (TTS)."""

from __future__ import annotations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.users import (
    get_or_create_user,
    get_user_language,
)
from utils.decorators import subscription_required
from utils.i18n import get_text

logger = logging.getLogger(__name__)

@subscription_required
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message or not message.text:
        return

    # Ignore commands (already handled by CommandHandler)
    if message.text.startswith("/"):
        return

    # Ensure user exists and get their language
    await get_or_create_user(user.id, user.username, user.first_name)
    lang = await get_user_language(user.id)

    text = message.text.strip()

    # 1. Check if user is actively in the TTS input state
    state = context.user_data.get("state")
    if state == "waiting_for_tts_text":
        # Clear the state
        context.user_data["state"] = None

        # Enforce length constraint (5,000 characters)
        if len(text) > 5000:
            await message.reply_text(
                get_text("err_too_long_tts", lang),
                parse_mode="MarkdownV2"
            )
            return

        # Store the text for voice synthesis
        context.user_data["tts_text"] = text

        # Step 1: Ask user to pick the TTS language
        select_lang_text = {
            "uz": "🌐 *Ovoz tilini tanlang:*",
            "ru": "🌐 *Выберите язык голоса:*",
            "en": "🌐 *Select voice language:*",
        }.get(lang, "🌐 *Select voice language:*")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="tts_lang:uz"),
                InlineKeyboardButton("🇷🇺 Русский",   callback_data="tts_lang:ru"),
                InlineKeyboardButton("🇺🇸 English",   callback_data="tts_lang:en"),
            ]
        ])

        await message.reply_text(
            select_lang_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            reply_to_message_id=message.message_id
        )
    else:
        # User sent generic text. Guide them to the /tts command
        tips = {
            "uz": "💡 *Professional ovoz yaratish uchun /tts buyrug'ini yuboring\\!*",
            "ru": "💡 *Чтобы создать профессиональную озвучку, отправьте команду /tts\\!*",
            "en": "💡 *To generate professional voiceovers, send the /tts command\\!*"
        }
        tip_text = tips.get(lang, tips["en"])
        await message.reply_text(
            tip_text,
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id
        )
