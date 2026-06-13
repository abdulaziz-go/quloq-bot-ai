"""
utils/referral.py — Referral ("invite friends") helpers.

Builds invite links / share buttons and credits successful referrals so that
BOTH the inviter and the newly-joined friend receive bonus credits.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.users import (
    get_or_create_user,
    get_user_language,
    process_referral,
    user_exists,
)
from utils.i18n import get_text

logger = logging.getLogger(__name__)


def referral_link(bot_username: str, user_id: int) -> str:
    """Deep link that pre-fills /start with the inviter's user_id as payload."""
    return f"https://t.me/{bot_username}?start={user_id}"


def invite_button(bot_username: str | None, user_id: int, lang: str) -> InlineKeyboardButton | None:
    """A button that opens Telegram's native share dialog with the invite link."""
    if not bot_username:
        return None
    link = referral_link(bot_username, user_id)
    share_text = get_text("referral_share_text", lang)
    url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(share_text, safe='')}"
    return InlineKeyboardButton(get_text("btn_invite_friends", lang), url=url)


def limit_keyboard(feature_key: str, user_id: int, bot_username: str | None, lang: str) -> InlineKeyboardMarkup:
    """Keyboard shown when a user hits a balance limit: Buy + Invite-friends."""
    rows = [[InlineKeyboardButton(get_text("btn_buy_more", lang), callback_data=f"buy_menu:{feature_key}")]]
    btn = invite_button(bot_username, user_id, lang)
    if btn:
        rows.append([btn])
    return InlineKeyboardMarkup(rows)


async def ensure_user_and_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Create the user if they are new and, on first creation via a referral link,
    credit BOTH the inviter and the new friend, then notify them. Idempotent —
    safe to call on every /start or membership verification.
    """
    user = update.effective_user
    if not user:
        return

    pending_ref = context.user_data.get("pending_ref")
    is_new = not await user_exists(user.id)

    await get_or_create_user(user.id, user.username, user.first_name, pending_ref or "(direct)")

    if is_new and pending_ref:
        try:
            ref_id = await process_referral(user.id, pending_ref)
        except Exception as e:  # never let referral bookkeeping break onboarding
            logger.warning("Referral processing failed: %s", e)
            ref_id = None

        if ref_id:
            await _notify_referrer(context, ref_id, user)
            # Tell the new friend about their welcome bonus.
            new_lang = await get_user_language(user.id)
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=get_text("referral_welcome_bonus", new_lang),
                    parse_mode="MarkdownV2",
                )
            except Exception:
                pass

    context.user_data.pop("pending_ref", None)


async def _notify_referrer(context: ContextTypes.DEFAULT_TYPE, ref_id: int, new_user) -> None:
    """Send the inviter a 'your friend joined, here are your rewards' message."""
    from utils.formatting import _escape
    ref_lang = await get_user_language(ref_id)
    friend = _escape(new_user.first_name or "your friend")
    try:
        await context.bot.send_message(
            chat_id=ref_id,
            text=get_text("referral_reward_earned", ref_lang, friend=friend),
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.debug("Could not notify referrer %s: %s", ref_id, e)
