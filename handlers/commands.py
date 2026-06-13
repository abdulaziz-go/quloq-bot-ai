"""handlers/commands.py — /start, /help, /status, /grant, /revoke."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import config
from database.users import (
    get_or_create_user,
    get_user,
    get_user_language,
)
from utils.decorators import admin_only, subscription_required
from utils.formatting import DIVIDER, _escape
from utils.i18n import get_lang_name, get_text
from utils.referral import limit_keyboard, invite_button, referral_link

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection on start, capturing & crediting referrals."""
    user = update.effective_user
    if not user:
        return

    # 1. Capture the referral payload (a numeric inviter user_id) BEFORE the
    #    channel gate, so it survives the join → verify step.
    if context.args and str(context.args[0]).isdigit():
        context.user_data["pending_ref"] = str(context.args[0])

    # 2. Channel membership gate (done manually so step 1 always runs).
    from utils.membership import is_user_member
    from utils.decorators import send_join_prompt
    if not await is_user_member(update, context):
        await send_join_prompt(update, context)
        return

    # 3. Ensure the user exists and credit the referral on first join via a link.
    from utils.referral import ensure_user_and_referral
    await ensure_user_and_referral(update, context)

    # Use 'en' as temporary for the very first welcome if no lang set
    lang = await get_user_language(user.id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang:en"),
        ]
    ])

    await update.message.reply_text(
        get_text("welcome", lang),
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
    )


@subscription_required
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    
    lang = await get_user_language(user.id)
    is_user_admin = user.id in config.admin_ids
    
    from utils.formatting import DIVIDER, _escape
    
    text = (
        "📖 *VoiceScribe AI — Help*\n\n"
        f"`{DIVIDER}`\n"
        "*Commands*\n"
        "/start \\— Welcome screen & instructions\n"
        "/help \\— This help message\n"
        "/status \\— Check your current plan\n"
    )
    
    if is_user_admin:
        text += (
            "\n*Admin Commands*\n"
            "/set\\_balance `<uid> <feat> <amt>` \\— Adjust balance\n"
            "/analytics \\— View bot statistics\n"
            "/users \\— Total user count\n"
            "/user `<query>` \\— Search for a user\n"
        )
        
    text += (
        f"\n`{DIVIDER}`\n"
        "*Tips*\n"
        "• Send any voice message or audio file\n"
        "• Works with forwarded messages too\n"
        "• Summarize or translate in seconds\n\n"
        "✨ *Premium features unlock after admin approval\\!*"
    )
    
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@subscription_required
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user balance and buy options."""
    user = update.effective_user
    if not user: return

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    lang = db_user.get("language", "en")
    
    from utils.formatting import _escape
    joined_safe = _escape(db_user.get("created_at", "Unknown").split()[0])

    # Pre-format balances
    bal_text = get_text(
        "balance_info", 
        lang,
        transcribe_bal=f"{db_user.get('balance_transcribe_sec', 0) // 60} min",
        summarize_bal=f"{db_user.get('balance_summarize_req', 0)} req",
        translate_bal=f"{db_user.get('balance_translate_req', 0)} req",
        extract_bal=f"{db_user.get('balance_extract_req', 0)} req",
        tts_bal=f"{db_user.get('balance_tts_req', 0)} req",
        image_bal=f"{db_user.get('balance_image_req', 0)} req",
    )

    text = get_text(
        "buy_status", 
        lang, 
        user_id=user.id, 
        lang_name=get_lang_name(lang), 
        joined=joined_safe
    ) + bal_text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("btn_top_up", lang), callback_data="buy_menu:main")],
        [InlineKeyboardButton(get_text("btn_back", lang), callback_data="back:main")]
    ])
    
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)


@subscription_required
async def cmd_tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt the user to enter text for Text-to-Speech voiceover generation."""
    user = update.effective_user
    if not user:
        return

    from database.users import check_balance, get_user_language
    lang = await get_user_language(user.id)

    # 1. Check if user has sufficient TTS request balance
    if not await check_balance(user.id, "tts"):
        await update.message.reply_text(
            get_text("limit_reached", lang, feature="Text-to-Speech"),
            parse_mode="MarkdownV2",
            reply_markup=limit_keyboard("tts", user.id, context.bot.username, lang)
        )
        return

    # 2. Set the user state to waiting for TTS text
    context.user_data["state"] = "waiting_for_tts_text"

    # 3. Prompt user for text
    await update.message.reply_text(
        get_text("prompt_tts_text", lang),
        parse_mode="MarkdownV2"
    )


@subscription_required
async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt the user for a text description to generate an AI image (Nano Banana)."""
    user = update.effective_user
    if not user:
        return

    from database.users import check_balance, get_user_language
    lang = await get_user_language(user.id)

    # 1. Check if user has sufficient image-generation balance
    if not await check_balance(user.id, "image"):
        await update.message.reply_text(
            get_text("limit_reached", lang, feature="Image Generation"),
            parse_mode="MarkdownV2",
            reply_markup=limit_keyboard("image", user.id, context.bot.username, lang)
        )
        return

    # 2. Set the user state to waiting for an image prompt
    context.user_data["state"] = "waiting_for_image_prompt"

    # 3. Prompt user for the image description
    await update.message.reply_text(
        get_text("prompt_image_prompt", lang),
        parse_mode="MarkdownV2"
    )


@subscription_required
async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's personal referral link and the rewards for inviting friends."""
    user = update.effective_user
    if not user:
        return

    await get_or_create_user(user.id, user.username, user.first_name)
    lang = await get_user_language(user.id)

    bot_username = context.bot.username
    link = referral_link(bot_username, user.id)

    # Link is wrapped in a code span inside the i18n string, so pass it raw.
    text = get_text("referral_invite_full", lang, link=link)

    btn = invite_button(bot_username, user.id, lang)
    keyboard = InlineKeyboardMarkup([[btn]]) if btn else None

    await update.message.reply_text(
        text,
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@admin_only

async def cmd_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /set_balance <user_id> <feature> <amount>"""
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: `/set_balance <user_id> <feature> <amount>`\n\n"
            "Features: `transcribe`, `summarize`, `translate`, `actions`, `tts`, `image`\n"
            "Example: `/set_balance 123456 transcribe 3600` \\(adds 1 hour\\)",
            parse_mode="MarkdownV2",
        )
        return

    try:
        target_id = int(context.args[0])
        feature = context.args[1].lower()
        amount = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments. ID and Amount must be integers.")
        return

    from database.users import add_balance, get_user
    existing = await get_user(target_id)
    if not existing:
        from database.users import get_or_create_user as _create
        await _create(target_id, None, None)

    success = await add_balance(target_id, feature, amount)
    if success:
        if amount > 0:
            from database.users import log_purchase
            revenue_uzs = 0
            if feature == "transcribe":
                revenue_uzs = int((amount / 3600.0) * 7000)   # 7 000 so'm per hour
            else:
                if amount <= 20:
                    revenue_uzs = amount * 350    # 7 000 / 20
                elif amount <= 100:
                    revenue_uzs = amount * 280    # 28 000 / 100
                else:
                    revenue_uzs = amount * 233    # 70 000 / 300
            await log_purchase(target_id, feature, amount, revenue_uzs)

        await update.message.reply_text(
            f"✅ Updated *{feature}* balance for `{target_id}` by `{amount}` units\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(f"❌ Failed to update balance. Check if feature `{feature}` is correct.")


@admin_only
async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from datetime import datetime, timedelta
    from database.users import get_daily_summary

    # ── Optional date argument: /analytics 12.06.2025 (DD.MM.YYYY) ──
    target_date = None  # None → today (UZ time)
    if context.args:
        raw = context.args[0].strip()
        parsed = None
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if not parsed:
            await update.message.reply_text(
                "❌ Invalid date\\. Use: `/analytics DD.MM.YYYY`\n"
                "Example: `/analytics 12.06.2025`",
                parse_mode="MarkdownV2",
            )
            return
        target_date = parsed.strftime("%Y-%m-%d")

    data = await get_daily_summary(target_date)

    def format_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.2f}M"
        elif n >= 1000:
            return f"{n / 1000:.1f}K"
        return str(n)

    total_sec = data["total_audio_sec"]
    audio_length_str = f"{int(total_sec // 60)}m {int(total_sec % 60)}s"

    # ── Pricing ──
    # Text/audio (Gemini text models): input $1.0/1M, output $2.5/1M.
    input_cost = (data["input_tokens"] / 1_000_000.0) * 1.0
    output_cost = (data["output_tokens"] / 1_000_000.0) * 2.5
    text_total_tokens = data["input_tokens"] + data["output_tokens"]
    # Image (Nano Banana): input text $0.30/1M, image output tokens $30/1M.
    img_input_cost = (data["image_input_tokens"] / 1_000_000.0) * 0.30
    img_output_cost = (data["image_output_tokens"] / 1_000_000.0) * 30.0
    image_cost = img_input_cost + img_output_cost
    grand_cost = input_cost + output_cost + image_cost

    # ── Date header (the actual day the data is for) ──
    day_dt = datetime.strptime(data["date"], "%Y-%m-%d")
    date_str = day_dt.strftime("%d.%m.%Y")
    is_today = data["date"] == (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")
    day_label = "Today" if is_today else day_dt.strftime("%A")

    # ── Per-feature usage (requests + distinct users) ──
    feat_meta = {
        "transcribe": "🎙 Transcription",
        "summarize":  "📝 Summaries",
        "translate":  "🌐 Translations",
        "actions":    "📌 Action Items",
        "tts":        "🔊 Text-to-Speech",
        "image":      "🎨 Image Generation",
    }
    usage_lines = []
    for item in data["feature_usage"]:
        name = feat_meta.get(item["action"], item["action"].capitalize())
        usage_lines.append(f"• {name}: *{item['requests']}* reqs by *{item['users']}* users")
    usage_block = "\n".join(usage_lines) if usage_lines else "• No feature usage on this day"

    credits_sold_parts = []
    for item in data["credits_sold"]:
        feat = item["feature"]
        amt = item["amount"]
        if feat == "transcribe":
            hrs = amt // 3600
            mins = (amt % 3600) // 60
            part = ""
            if hrs > 0:
                part += f"{hrs}h"
            if mins > 0:
                part += f" {mins}m"
            if not part:
                part = f"{amt}s"
            credits_sold_parts.append(part.strip())
        else:
            feat_name = {
                "tts": "TTS",
                "summarize": "Summaries",
                "translate": "Translations",
                "actions": "Tasks",
                "image": "Images",
            }.get(feat, feat.capitalize())
            credits_sold_parts.append(f"{amt} {feat_name}")

    credits_sold_str = ", ".join(credits_sold_parts) if credits_sold_parts else "None"

    text = (
        f"📊 *DAILY SUMMARY REPORT*\n"
        f"📅 *Date:* {date_str} ({day_label})\n\n"
        f"👥 *User Activity*\n"
        f"• New Signups: *{data['new_users']}*\n"
        f"• Joined via Referral Link: *{data['referral_signups']}*\n"
        f"• Daily Active Users (DAU): *{data['dau']}*\n"
        f"• Total Registered Users: *{data['total_users']}*\n\n"
        f"📂 *Feature Usage*\n"
        f"{usage_block}\n\n"
        f"🎙 *Voice Transcription*\n"
        f"• Total Transcriptions: *{data['total_transcriptions']}*\n"
        f"• Total Audio Length: *{audio_length_str}*\n\n"
        f"🤖 *AI Text/Audio Engine*\n"
        f"• Input Tokens: *{format_tokens(data['input_tokens'])}* (~${input_cost:.2f})\n"
        f"• Output Tokens: *{format_tokens(data['output_tokens'])}* (~${output_cost:.2f})\n"
        f"• Subtotal Tokens: *{format_tokens(text_total_tokens)}* (~${input_cost + output_cost:.2f})\n\n"
        f"🎨 *Image Generation (Nano Banana)*\n"
        f"• Images Generated: *{data['image_gens']}* by *{data['image_users']}* users\n"
        f"• Tokens (in/out): *{format_tokens(data['image_input_tokens'])}* / *{format_tokens(data['image_output_tokens'])}*\n"
        f"• Image Cost: *~${image_cost:.2f}*\n\n"
        f"🗣 *Text-to-Speech (TTS)*\n"
        f"• Generations: *{data['tts_gens']}* by *{data['tts_users']}* users\n"
        f"• Characters Synthesized: *{format_tokens(data['tts_chars'])}*\n\n"
        f"💰 *Total AI Cost:* ~${grand_cost:.2f}\n\n"
        f"💳 *Financials & Purchases*\n"
        f"• Successful Sales: *{data['purchase_count']}*\n"
        f"• Total Revenue: *{data['revenue_uzs']:,} UZS*\n"
        f"• Credits Distributed: *{credits_sold_str}*"
    )

    from utils.formatting import _escape
    escaped_text = _escape(text).replace("\\*", "*")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Growth: Hourly", callback_data="chart:growth:hourly"),
            InlineKeyboardButton("📊 Growth: Daily", callback_data="chart:growth:daily"),
        ],
        [
            InlineKeyboardButton("📊 Growth: Monthly", callback_data="chart:growth:monthly"),
            InlineKeyboardButton("📊 Growth: Yearly", callback_data="chart:growth:yearly"),
        ],
        [
            InlineKeyboardButton("💰 Tokens: Daily", callback_data="chart:usage:daily"),
            InlineKeyboardButton("💰 Tokens: Monthly", callback_data="chart:usage:monthly"),
            InlineKeyboardButton("💰 Tokens: Yearly", callback_data="chart:usage:yearly"),
        ]
    ])
    
    await update.message.reply_text(escaped_text, parse_mode="MarkdownV2", reply_markup=keyboard)


@admin_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.users import get_total_users
    total = await get_total_users()
    
    text = (
        "👥 *User Management*\n\n"
        f"Total Registered Users: *{total}*\n\n"
        "To search for a specific user, use:\n"
        "`/user <username_or_id>`"
    )
    from utils.formatting import _escape
    text = _escape(text).replace("\\*", "*").replace("\\`", "`")
    
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@admin_only
async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/user <username_or_id>`", parse_mode="MarkdownV2")
        return
        
    query = " ".join(context.args)
    from database.users import search_user
    results = await search_user(query)
    
    if not results:
        await update.message.reply_text(f"No users found matching '{query}'.")
        return
        
    lines = [f"🔍 *Search Results for '{query}'*:\n"]
    for u in results:
        name = u.get("first_name") or "Unknown"
        uname = f"@{u['username']}" if u.get("username") else "No username"
        joined = u.get("created_at", "").split()[0]
        
        lines.append(
            f"👤 *{name}* \\({uname}\\)\n"
            f"├ ID: `{u['user_id']}`\n"
            f"├ Lang: {u['language'].upper()}\n"
            f"└ Joined: {joined}\n"
        )
        
    text = "\n".join(lines)
    from utils.formatting import _escape
    text = _escape(text).replace("\\*", "*").replace("\\`", "`")
    
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@admin_only
async def cmd_db_dump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the database file to the admin."""
    import os
    if not os.path.exists(str(config.database_path)):
        await update.message.reply_text("❌ Database file not found.")
        return

    with open(str(config.database_path), "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=os.path.basename(str(config.database_path)),
            caption="📦 *VoiceScribe AI — Database Dump*",
            parse_mode="MarkdownV2",
        )
