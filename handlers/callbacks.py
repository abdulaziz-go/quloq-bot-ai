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
        summary, tokens = await summarize(transcript_row["text"])
        await log_usage(update.effective_user.id, "summarize", tokens=tokens)
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
        await log_usage(update.effective_user.id, "actions", tokens=actions.tokens)
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
        translation, tokens = await translate_text(transcript_row["text"], target_lang)
        await log_usage(update.effective_user.id, "translate", tokens=tokens)
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
        [InlineKeyboardButton(get_text("btn_translate", lang), callback_data=f"trans_menu:{key}")]
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
        ])
        await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
        return

    if feature == "transcribe":
        text = get_text("buy_menu_transcribe", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("60 Min ($1.00)", callback_data="buy:trans:3600")],
            [InlineKeyboardButton("3 Hours ($2.50)", callback_data="buy:trans:10800")],
            [InlineKeyboardButton("10 Hours ($7.00)", callback_data="buy:trans:36000")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "summarize":
        text = get_text("buy_menu_summarize", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 Sum ($1.00)", callback_data="buy:summarize:20")],
            [InlineKeyboardButton("100 Sum ($4.00)", callback_data="buy:summarize:100")],
            [InlineKeyboardButton("300 Sum ($10.00)", callback_data="buy:summarize:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "translate":
        text = get_text("buy_menu_translate", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 Trans ($1.00)", callback_data="buy:translate:20")],
            [InlineKeyboardButton("100 Trans ($4.00)", callback_data="buy:translate:100")],
            [InlineKeyboardButton("300 Trans ($10.00)", callback_data="buy:translate:300")],
            [InlineKeyboardButton(get_text("btn_back", lang), callback_data="buy_menu:main")],
        ])
    elif feature == "actions":
        text = get_text("buy_menu_actions", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 Extr ($1.00)", callback_data="buy:actions:20")],
            [InlineKeyboardButton("100 Extr ($4.00)", callback_data="buy:actions:100")],
            [InlineKeyboardButton("300 Extr ($10.00)", callback_data="buy:actions:300")],
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
