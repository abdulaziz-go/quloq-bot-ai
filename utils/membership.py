"""
utils/membership.py — Utility to check if a user is a member of the required channel.
"""

from __future__ import annotations

import logging
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from config import config

logger = logging.getLogger(__name__)

async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is a member of the required channel."""
    user = update.effective_user
    if not user:
        return False

    # Admins bypass the check
    if user.id in config.admin_ids:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=config.required_channel, 
            user_id=user.id
        )
        return member.status in [
            ChatMemberStatus.MEMBER, 
            ChatMemberStatus.ADMINISTRATOR, 
            ChatMemberStatus.OWNER
        ]
    except Exception as e:
        error_msg = str(e)
        if "Member list is inaccessible" in error_msg:
            logger.error(f"❌ Membership check failed for user {user.id}: Bot must be an ADMINISTRATOR in {config.required_channel}")
        else:
            logger.error(f"Error checking membership for user {user.id}: {e}")
        return False
