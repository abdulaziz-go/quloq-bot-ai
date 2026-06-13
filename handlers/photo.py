"""handlers/photo.py — Handle uploaded photos for AI image editing (Nano Banana)."""

from __future__ import annotations

import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.users import (
    check_balance,
    deduct_balance,
    get_or_create_user,
    get_user_language,
    log_usage,
)
from utils.decorators import subscription_required
from utils.i18n import get_text

logger = logging.getLogger(__name__)


@subscription_required
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sent a photo. If it has a caption, treat the caption as an AI edit
    instruction and return the transformed image. Otherwise, guide the user."""
    user = update.effective_user
    message = update.message
    if not user or not message or not message.photo:
        return

    await get_or_create_user(user.id, user.username, user.first_name)
    lang = await get_user_language(user.id)

    # Any pending text state (e.g. waiting_for_tts_text) is irrelevant for a photo.
    context.user_data["state"] = None

    instruction = (message.caption or "").strip()

    # 1. No caption → tell the user how to use the edit feature.
    if not instruction:
        await message.reply_text(
            get_text("prompt_image_edit_caption", lang),
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id,
        )
        return

    # 2. Enforce instruction length.
    if len(instruction) > 2000:
        await message.reply_text(
            get_text("err_too_long_image_prompt", lang),
            parse_mode="MarkdownV2",
        )
        return

    # 3. Balance check (image edits cost one image credit).
    if not await check_balance(user.id, "image"):
        from utils.referral import limit_keyboard
        await message.reply_text(
            get_text("limit_reached", lang, feature="Image Generation"),
            parse_mode="MarkdownV2",
            reply_markup=limit_keyboard("image", user.id, context.bot.username, lang)
        )
        return

    status_msg = await message.reply_text(
        get_text("editing_image", lang).replace("\\.", "."),
        reply_to_message_id=message.message_id,
    )

    try:
        from services.image_gen import edit_image

        # 4. Download the largest available photo size.
        photo_size = message.photo[-1]
        tg_file = await photo_size.get_file()
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        src_bytes = buf.getvalue()

        # 5. Run the AI edit.
        result = await edit_image(src_bytes, "image/jpeg", instruction)

        ext = "jpg" if "jpeg" in result.mime_type else "png"
        out = io.BytesIO(result.image_bytes)
        out.name = f"edited.{ext}"

        await message.reply_photo(
            photo=out,
            caption=get_text("image_success", lang),
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id,
            write_timeout=120,
            read_timeout=60,
            connect_timeout=30,
        )

        # Only charge once the edited image has actually been delivered.
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
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.exception("Image edit failed: %s", e)
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.reply_text(
            get_text("error_generic", lang),
            parse_mode="MarkdownV2",
        )
