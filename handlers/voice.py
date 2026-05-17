"""handlers/voice.py — Voice/audio message handler (F7 + transcription core)."""

from __future__ import annotations

import logging

from telegram import (
    Audio,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    Video,
    VideoNote,
    Voice,
)
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from database.users import (
    get_or_create_user,
    get_user_language,
    log_usage,
    save_transcript,
)
from services.transcriber import transcribe_telegram_file
from utils.decorators import subscription_required
from utils.formatting import format_transcript
from utils.i18n import get_text

logger = logging.getLogger(__name__)


def _build_keyboard(message_id: int, chat_id: int, lang: str) -> InlineKeyboardMarkup:
    """Build the localized action buttons."""
    key = f"{message_id}:{chat_id}"
    buttons = [
        [
            InlineKeyboardButton(get_text("btn_summarize", lang), callback_data=f"summarize:{key}"),
            InlineKeyboardButton(get_text("btn_actions", lang), callback_data=f"actions:{key}"),
        ],
        [
            InlineKeyboardButton(get_text("btn_translate", lang), callback_data=f"trans_menu:{key}"),
            InlineKeyboardButton(get_text("btn_tts", lang), callback_data=f"tts:{key}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def _resolve_audio(message: Message):
    if message.voice:
        v: Voice = message.voice
        return v, "voice.ogg", float(v.duration or 0)
    if message.audio:
        a: Audio = message.audio
        return a, a.file_name or "audio.mp3", float(a.duration or 0)
    if message.video_note:
        vn: VideoNote = message.video_note
        return vn, "video_note.mp4", float(vn.duration or 0)
    if message.video:
        vi: Video = message.video
        return vi, vi.file_name or "video.mp4", float(vi.duration or 0)
    return None


@subscription_required
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message: return

    # Ensure user exists and get their language
    await get_or_create_user(user.id, user.username, user.first_name)
    lang = await get_user_language(user.id)

    audio_data = _resolve_audio(message)
    if not audio_data: return

    tg_media, file_name, duration = audio_data
    
    # Enforce max duration constraint (20 minutes)
    if duration > 1200:
        await message.reply_text(
            get_text("err_too_long_audio", lang),
            parse_mode="MarkdownV2"
        )
        return

    # Wrap the plain loading text in bold tags for HTML
    loading_text = f"<b>{get_text('transcribing', lang)}</b>"
        
    from database.users import check_balance, deduct_balance
    if not await check_balance(user.id, "transcribe", requirement=int(duration)):
        await message.reply_text(
            get_text("limit_reached", lang, feature="Transcription"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:transcribe")
            ]])
        )
        return

    processing_msg = await message.reply_text(loading_text, parse_mode="HTML")
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    try:
        # Get the actual file object from Telegram servers
        tg_file = await context.bot.get_file(tg_media.file_id)
        
        result = await transcribe_telegram_file(tg_file, file_name, duration)
        await log_usage(
            user.id,
            "transcribe",
            tokens=result.tokens,
            duration_sec=duration,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens
        )
        await deduct_balance(user.id, "transcribe", amount=int(duration))
        await save_transcript(message.message_id, message.chat_id, user.id, result.text, result.language, duration)

        transcript_text = format_transcript(result.text, result.language, duration)
        keyboard = _build_keyboard(message.message_id, message.chat_id, lang)

        await processing_msg.edit_text(transcript_text, parse_mode="MarkdownV2", reply_markup=keyboard)

    except Exception as exc:
        logger.exception("Transcription failed: %s", exc)
        safe_error = str(exc)[:120]
        error_text = get_text("error_generic", lang).replace("\\.", ".")
        if error_text.count("*") >= 2:
            error_text = error_text.replace("*", "<b>", 1).replace("*", "</b>", 1)
            
        await processing_msg.edit_text(
            f"{error_text}\n\n<i>Error: {safe_error}</i>",
            parse_mode="HTML",
        )
