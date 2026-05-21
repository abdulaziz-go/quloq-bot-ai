"""handlers/voice.py — Voice/audio message handler (F7 + transcription core)."""

from __future__ import annotations

import asyncio
import logging

from google.genai import errors as genai_errors
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

from config import config
from database.users import (
    check_balance,
    deduct_balance,
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

# Per-user in-progress guard (max 1 transcription at a time per user)
_active_transcriptions: set[int] = set()
# Strong references so GC doesn't collect background tasks before they finish
_background_tasks: set[asyncio.Task] = set()


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

    # ── Video-specific validation ─────────────────────────────────────────────
    if message.video:
        mime = getattr(tg_media, "mime_type", "") or ""
        if not mime.startswith("video/"):
            err = {
                "uz": "❌ *Qo'llab\\-quvvatlanmaydigan fayl turi\\!*\n\nFaqat video fayllar qabul qilinadi \\(MP4, MOV, AVI va boshqalar\\)\\.",
                "ru": "❌ *Неподдерживаемый тип файла\\!*\n\nПринимаются только видеофайлы \\(MP4, MOV, AVI и др\\.\\)\\.",
                "en": "❌ *Unsupported file type\\!*\n\nOnly video files are accepted \\(MP4, MOV, AVI, etc\\.\\)\\.",
            }.get(lang, "❌ *Unsupported file type\\!* Only video files are accepted\\.")
            await message.reply_text(err, parse_mode="MarkdownV2")
            return

    # ── File size validation (Telegram Bot API limit: 20 MB) ─────────────────
    file_size = getattr(tg_media, "file_size", None)
    max_bytes = config.max_audio_size_mb * 1024 * 1024
    if file_size and file_size > max_bytes:
        size_mb = file_size / (1024 * 1024)
        err = {
            "uz": f"❌ *Fayl hajmi juda katta\\!*\n\nMaksimal ruxsat etilgan hajm: *{config.max_audio_size_mb} MB*\\. Sizning faylingiz: *{size_mb:.1f} MB*\\.\n\n💡 Iltimos, qisqaroq yoki kichikroq fayl yuboring\\.",
            "ru": f"❌ *Файл слишком большой\\!*\n\nМаксимально допустимый размер: *{config.max_audio_size_mb} МБ*\\. Ваш файл: *{size_mb:.1f} МБ*\\.\n\n💡 Пожалуйста, отправьте файл меньшего размера\\.",
            "en": f"❌ *File too large\\!*\n\nMaximum allowed size is *{config.max_audio_size_mb} MB*\\. Your file is *{size_mb:.1f} MB*\\.\n\n💡 Please send a smaller or shorter file\\.",
        }.get(lang, f"❌ *File too large\\!* Maximum is {config.max_audio_size_mb} MB\\.")
        await message.reply_text(err, parse_mode="MarkdownV2")
        return

    # ── Duration validation (max 20 minutes) ─────────────────────────────────
    if duration > 1200:
        await message.reply_text(
            get_text("err_too_long_audio", lang),
            parse_mode="MarkdownV2"
        )
        return

    # ── Per-user concurrency limit ────────────────────────────────────────────
    if user.id in _active_transcriptions:
        await message.reply_text(
            "⏳ Oldingi xabar hali ham qayta ishlanmoqda. Iltimos, biroz kuting.",
            parse_mode="HTML",
        )
        return

    if not await check_balance(user.id, "transcribe", requirement=int(duration)):
        await message.reply_text(
            get_text("limit_reached", lang, feature="Transcription"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:transcribe")
            ]])
        )
        return

    loading_text = f"<b>{get_text('transcribing', lang)}</b>"
    processing_msg = await message.reply_text(loading_text, parse_mode="HTML")
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    _active_transcriptions.add(user.id)

    async def _process() -> None:
        try:
            tg_file = await context.bot.get_file(tg_media.file_id)
            result = await transcribe_telegram_file(tg_file, file_name, duration)

            await log_usage(
                user.id,
                "transcribe",
                tokens=result.tokens,
                duration_sec=duration,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
            await deduct_balance(user.id, "transcribe", amount=int(duration))
            await save_transcript(
                message.message_id, message.chat_id, user.id,
                result.text, result.language, duration,
            )

            transcript_text = format_transcript(result.text, result.language, duration)
            keyboard = _build_keyboard(message.message_id, message.chat_id, lang)
            await processing_msg.edit_text(
                transcript_text, parse_mode="MarkdownV2", reply_markup=keyboard
            )

        except asyncio.TimeoutError:
            logger.warning(
                "Transcription timed out for user %s, file=%s", user.id, file_name
            )
            await processing_msg.edit_text(
                "⏱ Gemini server javob bermayapti. Iltimos, biroz kutib qayta urinib ko'ring.",
                parse_mode="HTML",
            )
        except RuntimeError as exc:
            logger.error(
                "Transcription runtime error for user %s, file=%s: %s",
                user.id, file_name, exc,
            )
            await processing_msg.edit_text(
                "⚠️ Gemini serverida vaqtinchalik nosozlik. Keyinroq qayta urinib ko'ring.",
                parse_mode="HTML",
            )
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if isinstance(code, int) and code >= 500:
                logger.error(
                    "Gemini server error %s for user %s: %s", code, user.id, exc
                )
                await processing_msg.edit_text(
                    "⚠️ Gemini serverida vaqtinchalik nosozlik. Keyinroq qayta urinib ko'ring.",
                    parse_mode="HTML",
                )
            else:
                logger.error(
                    "Gemini API error %s for user %s: %s", code, user.id, exc
                )
                await processing_msg.edit_text(
                    "❌ Xatolik yuz berdi. Admin bilan bog'laning.",
                    parse_mode="HTML",
                )
        except Exception as exc:
            logger.exception(
                "Transcription failed for user %s, file=%s: %s", user.id, file_name, exc
            )
            await processing_msg.edit_text(
                "❌ Xatolik yuz berdi. Admin bilan bog'laning.",
                parse_mode="HTML",
            )
        finally:
            _active_transcriptions.discard(user.id)

    task = asyncio.create_task(_process())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
