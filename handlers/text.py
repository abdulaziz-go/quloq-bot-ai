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
        if len(text) > 10000:
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
    elif state == "waiting_for_image_prompt":
        # Clear the state immediately so a failure doesn't trap the user
        context.user_data["state"] = None

        # Enforce prompt length constraint (2,000 characters)
        if len(text) > 2000:
            await message.reply_text(
                get_text("err_too_long_image_prompt", lang),
                parse_mode="MarkdownV2"
            )
            return

        from database.users import check_balance, deduct_balance, log_usage
        if not await check_balance(user.id, "image"):
            await message.reply_text(
                get_text("limit_reached", lang, feature="Image Generation"),
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:image")
                ]])
            )
            return

        status_msg = await message.reply_text(
            get_text("generating_image", lang).replace("\\.", "."),
            reply_to_message_id=message.message_id
        )

        try:
            import io
            from services.image_gen import generate_image

            result = await generate_image(text)

            ext = "jpg" if "jpeg" in result.mime_type else "png"
            photo = io.BytesIO(result.image_bytes)
            photo.name = f"image.{ext}"

            await message.reply_photo(
                photo=photo,
                caption=get_text("image_success", lang),
                parse_mode="MarkdownV2",
                reply_to_message_id=message.message_id,
                # Generous timeouts — generated PNGs can be 1–3 MB and slow to upload.
                write_timeout=120,
                read_timeout=60,
                connect_timeout=30,
            )

            # Only charge once the image has actually been delivered.
            await log_usage(
                user.id,
                "image",
                tokens=result.tokens,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
            await deduct_balance(user.id, "image")

            try:
                await status_msg.delete()
            except Exception:
                pass

        except RuntimeError:
            # Model returned no image (e.g. safety filter) — not charged.
            try:
                await status_msg.delete()
            except Exception:
                pass
            await message.reply_text(
                get_text("err_no_image", lang),
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.exception("Image generation failed: %s", e)
            try:
                await status_msg.delete()
            except Exception:
                pass
            await message.reply_text(
                get_text("error_generic", lang),
                parse_mode="MarkdownV2"
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
