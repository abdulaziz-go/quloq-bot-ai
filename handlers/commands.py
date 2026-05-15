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

logger = logging.getLogger(__name__)


@subscription_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection on start."""
    user = update.effective_user
    if not user:
        return

    await get_or_create_user(user.id, user.username, user.first_name)

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


@admin_only
async def cmd_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /set_balance <user_id> <feature> <amount>"""
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: `/set_balance <user_id> <feature> <amount>`\n\n"
            "Features: `transcribe`, `summarize`, `translate`, `actions`\n"
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
        await update.message.reply_text(
            f"✅ Updated *{feature}* balance for `{target_id}` by `{amount}` units\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(f"❌ Failed to update balance. Check if feature `{feature}` is correct.")


@admin_only
async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.users import get_analytics
    
    daily = await get_analytics(1)
    weekly = await get_analytics(7)
    monthly = await get_analytics(30)
    
    # Rough cost estimate based on Gemini 3.1 Flash ($0.15 / 1M tokens)
    def calc_cost(tokens):
        return (tokens / 1_000_000) * 0.15
        
    text = (
        "📊 *Bot Analytics Dashboard*\n\n"
        "*Past 24 Hours*\n"
        f"• Requests: {daily['total_requests']}\n"
        f"• Audio: {daily['total_duration']:.1f} sec\n"
        f"• Tokens: {daily['total_tokens']:,} \\(~${calc_cost(daily['total_tokens']):.4f}\\)\n\n"
        "*Past 30 Days*\n"
        f"• Requests: {monthly['total_requests']}\n"
        f"• Audio: {monthly['total_duration']:.1f} sec\n"
        f"• Tokens: {monthly['total_tokens']:,} \\(~${calc_cost(monthly['total_tokens']):.2f}\\)\n\n"
        "📈 *Visual Charts*"
    )
    
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
    
    # Escape dots, hyphens etc for MarkdownV2
    from utils.formatting import _escape
    text = _escape(text).replace("\\*", "*") 
    
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)


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
