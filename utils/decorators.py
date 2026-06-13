"""utils/decorators.py — Reusable handler decorators."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import config
from database.users import is_premium, get_user_language
from utils.formatting import format_premium_locked, _escape
from utils.i18n import get_text
from utils.membership import is_user_member

logger = logging.getLogger(__name__)


def admin_only(func: Callable) -> Callable:
    """Decorator: Only allow messages from ADMIN_IDS."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in config.admin_ids:
            await update.message.reply_text(
                "⛔ This command is restricted to bot administrators.",
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def premium_required(feature_name: str):
    """Decorator factory: Gate a callback on premium status."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return
            premium = await is_premium(user.id)
            if not premium:
                await update.callback_query.answer(
                    "🔒 Premium feature — contact admin to unlock.",
                    show_alert=True,
                )
                return
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


async def send_join_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the 'join the required channel' message with join + verify buttons."""
    user = update.effective_user
    if not user:
        return
    lang = await get_user_language(user.id)

    channel_handle = config.required_channel.lstrip("@")
    channel_url = f"https://t.me/{channel_handle}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("btn_join_channel", lang), url=channel_url)],
        [InlineKeyboardButton(get_text("btn_check_sub", lang), callback_data="check_sub")]
    ])
    text = get_text("sub_required", lang, channel=config.required_channel)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)


def subscription_required(func: Callable) -> Callable:
    """Decorator: Gate a handler on channel membership status."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        if await is_user_member(update, context):
            return await func(update, context, *args, **kwargs)

        await send_join_prompt(update, context)
        return
    return wrapper
