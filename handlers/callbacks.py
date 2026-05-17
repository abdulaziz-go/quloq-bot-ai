"""handlers/callbacks.py — Inline button callbacks for language selection, transcription actions, and translation."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.users import (
    get_transcript,
    get_user_language,
    is_premium,
    log_usage,
    set_user_language,
)
from services.action_detector import ActionItems, extract_actions
from services.summarizer import summarize
from services.translator import translate_text
from utils.formatting import (
    format_action_copy_text,
    format_actions,
    format_summary,
)
from utils.i18n import get_text

logger = logging.getLogger(__name__)


# ── Locked feature handler ────────────────────────────────────────────────────

async def callback_locked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    lang = await get_user_language(update.effective_user.id)
    await query.answer(
        get_text("error_generic", lang).strip("❌ *!"),
        show_alert=True,
    )


# ── Language Selection ────────────────────────────────────────────────────────

async def callback_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection buttons (lang:uz, lang:ru, lang:en)."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    lang_code = query.data.split(":")[1]
    await set_user_language(user.id, lang_code)

    await query.answer(get_text("lang_selected", lang_code).strip("✅ *!"))
    await query.edit_message_text(
        get_text("lang_selected", lang_code) + "\n\n" + get_text("instructions", lang_code),
        parse_mode="MarkdownV2",
    )


# ── Summarize ─────────────────────────────────────────────────────────────────

async def callback_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)
    await query.answer(get_text("summarizing", lang).strip("⏳ *!"))

    try:
        _, message_id_str, chat_id_str = query.data.split(":")
        message_id, chat_id = int(message_id_str), int(chat_id_str)
    except (ValueError, AttributeError):
        return

    transcript_row = await get_transcript(message_id, chat_id)
    if not transcript_row:
        return

    # Constraint: Max text length
    if len(transcript_row["text"]) > 30000:
        await query.message.reply_text(
            get_text("err_too_long_text", lang),
            parse_mode="MarkdownV2"
        )
        return

    from database.users import check_balance, deduct_balance
    if not await check_balance(update.effective_user.id, "summarize"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Summarization"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:summarize")
            ]])
        )
        return

    # Loading state
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text("summarizing", lang), callback_data="noop")
        ]])
    )

    try:
        summary, tokens, in_t, out_t = await summarize(transcript_row["text"])
        await log_usage(
            update.effective_user.id, 
            "summarize", 
            tokens=tokens,
            input_tokens=in_t,
            output_tokens=out_t
        )
        await deduct_balance(update.effective_user.id, "summarize")
        await query.message.reply_text(
            format_summary(summary), 
            parse_mode="MarkdownV2",
            reply_to_message_id=message_id
        )
        await _restore_keyboard(query, message_id, chat_id, lang)
    except Exception:
        await _restore_keyboard(query, message_id, chat_id, lang)


# ── Extract Actions ───────────────────────────────────────────────────────────

async def callback_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)
    
    from database.users import check_balance, deduct_balance
    if not await check_balance(user.id, "actions"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Action Extraction"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:actions")
            ]])
        )
        return

    await query.answer(get_text("extracting", lang).strip("⏳ *!"))

    try:
        _, message_id_str, chat_id_str = query.data.split(":")
        message_id, chat_id = int(message_id_str), int(chat_id_str)
    except (ValueError, AttributeError):
        return

    transcript_row = await get_transcript(message_id, chat_id)
    if not transcript_row:
        return

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text("extracting", lang), callback_data="noop")
        ]])
    )

    try:
        actions = await extract_actions(transcript_row["text"])
        await log_usage(
            update.effective_user.id, 
            "actions", 
            tokens=actions.tokens,
            input_tokens=actions.input_tokens,
            output_tokens=actions.output_tokens
        )
        await deduct_balance(update.effective_user.id, "actions")
        formatted = format_actions(actions)
        keyboard = _build_action_keyboard(actions, message_id, chat_id, lang)
        await query.message.reply_text(
            formatted, 
            parse_mode="MarkdownV2", 
            reply_markup=keyboard,
            reply_to_message_id=message_id
        )
        await _restore_keyboard(query, message_id, chat_id, lang)
    except Exception:
        await _restore_keyboard(query, message_id, chat_id, lang)


# ── Translation ───────────────────────────────────────────────────────────────

async def callback_translate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language choices for translation."""
    query = update.callback_query
    if not query: return
    
    lang = await get_user_language(update.effective_user.id)
    _, msg_id, chat_id = query.data.split(":")
    key = f"{msg_id}:{chat_id}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data=f"trans:uz:{key}"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data=f"trans:ru:{key}"),
            InlineKeyboardButton("🇺🇸 English", callback_data=f"trans:en:{key}"),
        ],
        [InlineKeyboardButton(get_text("btn_back", lang), callback_data=f"back:{key}")]
    ])

    await query.edit_message_reply_markup(reply_markup=keyboard)


async def callback_translate_exec(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute translation."""
    query = update.callback_query
    if not query: return

    lang = await get_user_language(update.effective_user.id)
    
    from database.users import check_balance, deduct_balance
    if not await check_balance(update.effective_user.id, "translate"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Translation"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:translate")
            ]])
        )
        return

    # data: trans:target_lang:msg_id:chat_id
    _, target_lang, msg_id, chat_id = query.data.split(":")
    
    await query.answer(get_text("translating", lang).strip("⏳ *!"))
    
    transcript_row = await get_transcript(int(msg_id), int(chat_id))
    if not transcript_row: return

    # Constraint: Max text length
    if len(transcript_row["text"]) > 30000:
        await query.message.reply_text(
            get_text("err_too_long_text", lang),
            parse_mode="MarkdownV2"
        )
        return

    try:
        translation, tokens, in_t, out_t = await translate_text(transcript_row["text"], target_lang)
        await log_usage(
            update.effective_user.id, 
            "translate", 
            tokens=tokens,
            input_tokens=in_t,
            output_tokens=out_t
        )
        await deduct_balance(update.effective_user.id, "translate")
        
        from utils.formatting import _escape
        translation_safe = _escape(translation)
        
        await query.message.reply_text(
            f"🌐 *Translation \\({target_lang.upper()}\\)*\n\n{translation_safe}",
            parse_mode="MarkdownV2",
            reply_to_message_id=int(msg_id)
        )
        await _restore_keyboard(query, int(msg_id), int(chat_id), lang)
    except Exception:
        await _restore_keyboard(query, int(msg_id), int(chat_id), lang)

def get_tts_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Build the premium voice model selection keyboard with select and preview buttons."""
    if lang not in ("uz", "ru", "en"):
        lang = "en"
        
    if lang == "uz":
        buttons = [
            [
                InlineKeyboardButton("👦 Sardor (Erkak)", callback_data="tts_sel:uz-UZ-SardorNeural"),
                InlineKeyboardButton("👧 Madina (Ayol)", callback_data="tts_sel:uz-UZ-MadinaNeural"),
            ],
            [
                InlineKeyboardButton("🎧 Sardor (Eshitish)", callback_data="tts_prev:uz-UZ-SardorNeural"),
                InlineKeyboardButton("🎧 Madina (Eshitish)", callback_data="tts_prev:uz-UZ-MadinaNeural"),
            ]
        ]
    elif lang == "ru":
        buttons = [
            [
                InlineKeyboardButton("👦 Дмитрий (Мужской)", callback_data="tts_sel:ru-RU-DmitryNeural"),
                InlineKeyboardButton("👧 Светлана (Женский)", callback_data="tts_sel:ru-RU-SvetlanaNeural"),
            ],
            [
                InlineKeyboardButton("🎧 Дмитрий (Послушать)", callback_data="tts_prev:ru-RU-DmitryNeural"),
                InlineKeyboardButton("🎧 Светлана (Послушать)", callback_data="tts_prev:ru-RU-SvetlanaNeural"),
            ]
        ]
    else:  # en
        buttons = [
            [
                InlineKeyboardButton("👦 Guy (Male)", callback_data="tts_sel:en-US-GuyNeural"),
                InlineKeyboardButton("👧 Jenny (Female)", callback_data="tts_sel:en-US-JennyNeural"),
            ],
            [
                InlineKeyboardButton("🎧 Guy (Listen)", callback_data="tts_prev:en-US-GuyNeural"),
                InlineKeyboardButton("🎧 Jenny (Listen)", callback_data="tts_prev:en-US-JennyNeural"),
            ]
        ]
    return InlineKeyboardMarkup(buttons)


async def callback_tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show premium voice selection menu for a transcription."""
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)
    
    from database.users import check_balance
    if not await check_balance(user.id, "tts"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Text-to-Speech"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:tts")
            ]])
        )
        await query.answer()
        return

    # Extract message and chat IDs
    # data: tts:message_id:chat_id
    try:
        _, msg_id, chat_id = query.data.split(":")
    except (ValueError, AttributeError):
        return

    transcript_row = await get_transcript(int(msg_id), int(chat_id))
    if not transcript_row:
        return

    # Check constraint: Max text length for TTS
    if len(transcript_row["text"]) > 10000:
        await query.message.reply_text(
            get_text("err_too_long_tts", lang),
            parse_mode="MarkdownV2"
        )
        await query.answer()
        return

    # Save to user session
    context.user_data["tts_text"] = transcript_row["text"]

    # Step 1: Show language selection
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
    await query.message.reply_text(
        select_lang_text,
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
        reply_to_message_id=int(msg_id)
    )
    await query.answer()


async def callback_tts_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle TTS language selection, then show voice model keyboard for that language."""
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)

    from database.users import check_balance
    if not await check_balance(user.id, "tts"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Text-to-Speech"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:tts")
            ]])
        )
        await query.answer()
        return

    text = context.user_data.get("tts_text")
    if not text:
        await query.answer(get_text("err_no_tts_text", lang).strip("❌ *!."), show_alert=True)
        return

    # data: tts_lang:uz / tts_lang:ru / tts_lang:en
    _, chosen_lang = query.data.split(":")

    keyboard = get_tts_keyboard(chosen_lang)
    await query.edit_message_text(
        get_text("select_voice_model", lang),
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
    )
    await query.answer()


async def callback_tts_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle generation of the saved text using the chosen voice model."""
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)
    
    # 1. Check balance
    from database.users import check_balance, deduct_balance
    if not await check_balance(user.id, "tts"):
        await query.message.reply_text(
            get_text("limit_reached", lang, feature="Text-to-Speech"),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data="buy_menu:tts")
            ]])
        )
        await query.answer()
        return

    # 2. Retrieve the text to synthesize
    text = context.user_data.get("tts_text")
    if not text:
        await query.message.reply_text(
            get_text("err_no_tts_text", lang),
            parse_mode="MarkdownV2"
        )
        await query.answer()
        return

    # data: tts_sel:voice_id
    _, voice_id = query.data.split(":")

    # 3. Show generation status
    await query.answer(get_text("generating_voice", lang).strip("⏳ *!"))
    
    # Update button to loading state
    original_markup = query.message.reply_markup
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text("generating_voice", lang), callback_data="noop")
        ]])
    )

    try:
        from services.tts import text_to_speech
        import io

        # 4. Synthesize voice
        audio_bytes = await text_to_speech(text, voice_id)
        
        # 5. Log and deduct balance
        await log_usage(user.id, "tts", tokens=len(text))
        await deduct_balance(user.id, "tts")

        # 6. Prepare and send the voice note
        voice_file = io.BytesIO(audio_bytes)
        voice_file.name = "voice.mp3"

        caption = get_text("tts_success", lang)

        await query.message.reply_voice(
            voice=voice_file,
            caption=caption,
            parse_mode="MarkdownV2",
            reply_to_message_id=query.message.reply_to_message.message_id if query.message.reply_to_message else None
        )
        
        # Clear selected text session and delete the selection prompt
        context.user_data["tts_text"] = None
        try:
            await query.message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception("TTS generation callback failed: %s", e)
        # Restore the selection keyboard in case of error
        try:
            await query.edit_message_reply_markup(reply_markup=original_markup)
        except Exception:
            pass
        error_text = get_text("error_generic", lang).replace("\\.", ".")
        await query.message.reply_text(f"{error_text}\n\n_Error: {str(e)[:120]}_", parse_mode="Markdown")


async def callback_tts_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle playing a quick pre-defined voice preview sample for a chosen model (free)."""
    query = update.callback_query
    user = update.effective_user
    if not user or not query:
        return

    lang = await get_user_language(user.id)
    
    # data: tts_prev:voice_id
    _, voice_id = query.data.split(":")

    # Map voice_id to localized preview intro strings
    # Keys in i18n: preview_text_uz_Sardor, preview_text_uz_Madina, etc.
    voice_key = "en_Jenny"
    voice_name = "Jenny"
    voice_lang = "en"
    if "Sardor" in voice_id:
        voice_key = "uz_Sardor"
        voice_name = "Sardor"
        voice_lang = "uz"
    elif "Madina" in voice_id:
        voice_key = "uz_Madina"
        voice_name = "Madina"
        voice_lang = "uz"
    elif "Dmitry" in voice_id:
        voice_key = "ru_Dmitry"
        voice_name = "Дмитрий"
        voice_lang = "ru"
    elif "Svetlana" in voice_id:
        voice_key = "ru_Svetlana"
        voice_name = "Светлана"
        voice_lang = "ru"
    elif "Guy" in voice_id:
        voice_key = "en_Guy"
        voice_name = "Guy"
        voice_lang = "en"
    
    preview_key = f"preview_text_{voice_key}"
    preview_text = get_text(preview_key, voice_lang).replace("\\!", "!").replace("\\.", ".")

    # Answer query
    playing_label = {
        "uz": f"🎧 {voice_name} ovozi eshitilmoqda...",
        "ru": f"🎧 Воспроизведение демо {voice_name}...",
        "en": f"🎧 Playing preview of {voice_name}..."
    }.get(lang, f"🎧 Playing preview of {voice_name}...")
    
    await query.answer(playing_label)

    try:
        from services.tts import text_to_speech
        import io

        # Synthesize the preview text (free)
        audio_bytes = await text_to_speech(preview_text, voice_id)

        # Prepare and send the voice note
        voice_file = io.BytesIO(audio_bytes)
        voice_file.name = "preview.mp3"

        caption_label = {
            "uz": f"🎧 {voice_name} ovozi namunasi",
            "ru": f"🎧 Демонстрация голоса {voice_name}",
            "en": f"🎧 Voice sample of {voice_name}"
        }.get(lang, f"🎧 Voice sample of {voice_name}")

        await query.message.reply_voice(
            voice=voice_file,
            caption=caption_label,
            reply_to_message_id=query.message.message_id
        )

    except Exception as e:
        logger.exception("TTS preview callback failed: %s", e)
        error_text = get_text("error_generic", lang).replace("\\.", ".")
        await query.message.reply_text(f"{error_text}\n\n_Error: {str(e)[:120]}_", parse_mode="Markdown")



async def callback_copy_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    lang = await get_user_language(update.effective_user.id)
    try:
        _, msg_id, chat_id = query.data.split(":")
        transcript_row = await get_transcript(int(msg_id), int(chat_id))
        if transcript_row:
            # Constraint: Max text length
            if len(transcript_row["text"]) > 30000:
                await query.message.reply_text(
                    get_text("err_too_long_text", lang),
                    parse_mode="MarkdownV2"
                )
                return

            actions = await extract_actions(transcript_row["text"])
            plain = format_action_copy_text(actions)
            await query.answer("📋")
            await query.message.reply_text(f"📋 *Action Items*\n\n`{plain}`", parse_mode="MarkdownV2")
    except Exception:
        pass


async def callback_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query: await update.callback_query.answer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_action_keyboard(actions: ActionItems, mid: int, cid: int, lang: str) -> InlineKeyboardMarkup | None:
    if actions.is_empty: return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("📋 Copy All", callback_data=f"copy:{mid}:{cid}")]])


async def _restore_keyboard(query, mid: int, cid: int, lang: str) -> None:
    key = f"{mid}:{cid}"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text("btn_summarize", lang), callback_data=f"summarize:{key}"),
            InlineKeyboardButton(get_text("btn_actions", lang), callback_data=f"actions:{key}"),
        ],
        [
            InlineKeyboardButton(get_text("btn_translate", lang), callback_data=f"trans_menu:{key}"),
            InlineKeyboardButton(get_text("btn_tts", lang), callback_data=f"tts:{key}"),
        ]
    ])
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

async def callback_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    _, mid, cid = query.data.split(":")
    lang = await get_user_language(update.effective_user.id)
    await _restore_keyboard(query, int(mid), int(cid), lang)


# ── Buying & Plans ────────────────────────────────────────────────────────────

async def callback_buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    
    lang = await get_user_language(update.effective_user.id)
    # data: buy_menu:feature
    feature = query.data.split(":")[1]
    
    if feature == "main":
        text = get_text("buy_menu_main", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text("btn_transcription", lang), callback_data="buy_menu:transcribe")],
            [InlineKeyboardButton(get_text("btn_summarization", lang), callback_data="buy_menu:summarize")],
            [InlineKeyboardButton(get_text("btn_translation", lang), callback_data="buy_menu:translate")],
            [InlineKeyboardButton(get_text("btn_actions_extr", lang), callback_data="buy_menu:actions")],
            [InlineKeyboardButton(get_text("btn_tts_feature", lang), callback_data="buy_menu:tts")],
        ])
        await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
        return

    if feature == "transcribe":
        text = get_text("buy_menu_transcribe", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("60 daqiqa — 7 000 so'm", callback_data="buy:trans:3600")],
            [InlineKeyboardButton("3 soat — 21 000 so'm",   callback_data="buy:trans:10800")],
            [InlineKeyboardButton("10 soat — 70 000 so'm",  callback_data="buy:trans:36000")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "summarize":
        text = get_text("buy_menu_summarize", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 ta — 7 000 so'm",  callback_data="buy:summarize:20")],
            [InlineKeyboardButton("100 ta — 28 000 so'm", callback_data="buy:summarize:100")],
            [InlineKeyboardButton("300 ta — 70 000 so'm", callback_data="buy:summarize:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "translate":
        text = get_text("buy_menu_translate", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 ta — 7 000 so'm",  callback_data="buy:translate:20")],
            [InlineKeyboardButton("100 ta — 28 000 so'm", callback_data="buy:translate:100")],
            [InlineKeyboardButton("300 ta — 70 000 so'm", callback_data="buy:translate:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "actions":
        text = get_text("buy_menu_actions", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 ta — 7 000 so'm",  callback_data="buy:actions:20")],
            [InlineKeyboardButton("100 ta — 28 000 so'm", callback_data="buy:actions:100")],
            [InlineKeyboardButton("300 ta — 70 000 so'm", callback_data="buy:actions:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "tts":
        text = get_text("buy_menu_tts", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 ta — 7 000 so'm",  callback_data="buy:tts:20")],
            [InlineKeyboardButton("100 ta — 28 000 so'm", callback_data="buy:tts:100")],
            [InlineKeyboardButton("300 ta — 70 000 so'm", callback_data="buy:tts:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    
    try:
        await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)


async def callback_buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    
    user = update.effective_user
    lang = await get_user_language(user.id)
    # data: buy:feature:amount
    _, feat_short, amount_str = query.data.split(":")
    amount = int(amount_str)
    
    feature = {
        "trans": "transcribe",
        "summarize": "summarize",
        "translate": "translate",
        "actions": "actions",
    }.get(feat_short, feat_short)

    # Determine plan display name
    plan_name = ""
    if feature == "transcribe":
        plan_name = f"{amount // 60} Minutes"
    else:
        plan_name = f"{amount} Requests"

    from config import config
    from utils.formatting import _escape

    # 1. Notify User
    await query.message.edit_text(
        get_text("buy_request_sent", lang, plan=_escape(plan_name)),
        parse_mode="MarkdownV2"
    )

    # 2. Notify Admins
    admin_msg = get_text(
        "admin_buy_request", "en",
        name=_escape(user.full_name),
        user_id=user.id,
        username=_escape(user.username or "none"),
        plan=_escape(plan_name),
        feature=feature,
        amount=amount
    )

    for admin_id in config.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_msg,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.warning("Could not notify admin %s: %s", admin_id, e)
    
    await query.answer()


async def callback_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'I have joined' button."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    from utils.membership import is_user_member
    if await is_user_member(update, context):
        await query.answer("✅ Thank you for joining!", show_alert=True)
        # Show the language selection menu (start screen)
        lang = await get_user_language(user.id)
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang:en"),
            ]
        ])

        await query.edit_message_text(
            get_text("welcome", lang),
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
    else:
        lang = await get_user_language(user.id)
        await query.answer("❌ You haven't joined the channel yet.", show_alert=True)


async def callback_admin_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin chart requests."""
    query = update.callback_query
    if not query: return
    
    # Check if admin (safety check again)
    from config import config
    if update.effective_user.id not in config.admin_ids:
        await query.answer("Admin only.", show_alert=True)
        return

    # data: chart:type:period
    _, chart_type, period = query.data.split(":")
    
    await query.answer("📊 Generating chart...")
    
    from database.users import get_user_growth_data, get_usage_stats_data
    from utils.charts import generate_chart_url
    
    if chart_type == "growth":
        data_rows = await get_user_growth_data(period)
        labels = [r["label"] for r in data_rows]
        values = [r["count"] for r in data_rows]
        title = f"User Growth ({period.capitalize()})"
        color = "rgb(54, 162, 235)"
    else:
        data_rows = await get_usage_stats_data(period)
        labels = [r["label"] for r in data_rows]
        values = [r["total_tokens"] for r in data_rows]
        title = f"Token Usage ({period.capitalize()})"
        color = "rgb(255, 99, 132)"

    if not labels:
        await query.message.reply_text("❌ No data available for this period.")
        return

    url = generate_chart_url(labels, values, title, color)
    
    from utils.formatting import _escape
    safe_title = _escape(title).replace("\\*", "*")

    await query.message.reply_photo(
        photo=url,
        caption=f"📈 *{safe_title}*\nGenerated based on real\\-time data\\.",
        parse_mode="MarkdownV2"
    )
