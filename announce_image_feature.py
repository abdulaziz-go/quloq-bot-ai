"""
announce_image_feature.py — ONE-TIME image-generation launch + announcement.

What it does (only once, ever):
  1. Quietly grants every existing user a starting image-generation balance
     (uses MAX, so users who already have credits never lose anything). The
     announcement itself does NOT mention any limit.
  2. Generates one attractive sample image (via "Nano Banana") and broadcasts
     it as a photo to every user, with a localised caption announcing both the
     text→image generation and the new photo-editing capability. The caption
     links to @QuloqAiBot.

It is guarded by a flag in the `bot_settings` table, so even if the bot
restarts many times the grant is applied and the broadcast is sent only once.

Wired into bot startup via `post_init` in bot.py.
"""

from __future__ import annotations

import asyncio
import io
import logging

import aiosqlite

from database.db import get_db_path
from database.users import get_setting, set_setting

logger = logging.getLogger(__name__)

# Unique key — bump the suffix to run a NEW campaign (re-grants + re-broadcasts).
_FLAG_KEY = "image_feature_announced_v3"

# Starting image credits gifted to every existing user (not shown in the message).
_FREE_IMAGE_CREDITS = 30

# Prompt used to render the eye-catching promo image attached to the broadcast.
_PROMO_PROMPT = (
    "A fun, eye-catching before-and-after promo illustration: on the left an "
    "ordinary photo of a smiling young person, on the right the same person "
    "magically transformed into a vibrant superhero/anime version with glowing "
    "AI sparkles between them, a cute banana mascot, bright modern digital art, "
    "high detail, poster style."
)

# ── Localised announcement captions (HTML parse mode, ≤1024 chars) ──────────────
_MESSAGES = {
    "uz": (
        "🎨 <b>YANGI: AI bilan rasm sehri!</b> 🪄\n\n"
        "Endi o'zingizning yoki <b>do'stlaringizning rasmini</b> menga tashlang — "
        "men ularni AI yordamida tubdan o'zgartirib beraman! 🤩\n\n"
        "📸 <b>Nimalar qila olaman?</b>\n"
        "• Rasmni anime, 3D yoki rassom uslubiga aylantirish 🎭\n"
        "• Fon, kiyim yoki soch turini o'zgartirish 💇\n"
        "• Do'stingizni kosmosga, dengiz bo'yiga yoki ertak olamiga \"joylashtirish\" 🚀\n"
        "• Istalgan boshqa g'oya — shunchaki yozing!\n\n"
        "✨ <b>Qanday ishlaydi?</b>\n"
        "📤 Rasmni yuboring va izohda nima qilishni yozing\n"
        "🖌 Yoki /image bilan noldan rasm yarating\n\n"
        "👉 Hoziroq do'stingizning rasmini tashlab sinab ko'ring! 🔥\n\n@QuloqAiBot"
    ),
    "ru": (
        "🎨 <b>НОВОЕ: магия фото с AI!</b> 🪄\n\n"
        "Теперь пришлите мне своё фото или <b>фото друзей</b> — и я преображу их "
        "с помощью AI! 🤩\n\n"
        "📸 <b>Что я умею?</b>\n"
        "• Превратить фото в стиль аниме, 3D или картину 🎭\n"
        "• Изменить фон, одежду или причёску 💇\n"
        "• «Отправить» друга в космос, на пляж или в сказку 🚀\n"
        "• И любую другую идею — просто напишите!\n\n"
        "✨ <b>Как это работает?</b>\n"
        "📤 Отправьте фото с подписью, что сделать\n"
        "🖌 Или создайте изображение с нуля через /image\n\n"
        "👉 Скорее пришлите фото друга и попробуйте! 🔥\n\n@QuloqAiBot"
    ),
    "en": (
        "🎨 <b>NEW: AI photo magic!</b> 🪄\n\n"
        "Now send me a photo of yourself or <b>your friends</b> — and I'll "
        "transform them with AI! 🤩\n\n"
        "📸 <b>What can I do?</b>\n"
        "• Turn a photo into anime, 3D, or painting style 🎭\n"
        "• Change the background, outfit, or hairstyle 💇\n"
        "• Drop your friend into space, a beach, or a fairy tale 🚀\n"
        "• Any other idea — just describe it!\n\n"
        "✨ <b>How does it work?</b>\n"
        "📤 Send a photo with a caption of what to do\n"
        "🖌 Or create an image from scratch with /image\n\n"
        "👉 Send a friend's photo and try it now! 🔥\n\n@QuloqAiBot"
    ),
}


async def _grant_free_credits() -> int:
    """Raise every user's image balance up to the starting amount. Returns rows touched."""
    async with aiosqlite.connect(get_db_path()) as db:
        cur = await db.execute(
            """
            UPDATE users SET
                balance_image_req = MAX(balance_image_req, ?),
                updated_at        = datetime('now')
            """,
            (_FREE_IMAGE_CREDITS,),
        )
        await db.commit()
        return cur.rowcount


async def _all_recipients() -> list[tuple[int, str]]:
    """Return [(user_id, language), ...] for every registered user."""
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute("SELECT user_id, language FROM users") as cur:
            rows = await cur.fetchall()
            return [(r[0], r[1] or "en") for r in rows]


async def _make_promo_image() -> bytes | None:
    """Render one attractive promo image to attach to the broadcast. None on failure."""
    try:
        from services.image_gen import generate_image
        result = await generate_image(_PROMO_PROMPT)
        logger.info("Promo image generated (%d bytes).", len(result.image_bytes))
        return result.image_bytes
    except Exception as e:
        logger.warning("Could not generate promo image, falling back to text: %s", e)
        return None


async def run_image_announcement(application) -> None:
    """Entry point — grant credits and broadcast once. Safe to call on every startup."""
    if await get_setting(_FLAG_KEY):
        logger.info("Image feature already announced (%s) — skipping.", _FLAG_KEY)
        return

    logger.info("🎨 Running ONE-TIME image-feature grant + announcement…")

    touched = await _grant_free_credits()
    logger.info("Image credits granted for %d users.", touched)

    promo_bytes = await _make_promo_image()

    recipients = await _all_recipients()
    logger.info("Broadcasting image-feature announcement to %d users…", len(recipients))

    bot = application.bot
    sent = 0
    failed = 0
    promo_file_id: str | None = None  # reuse Telegram's file_id after first upload

    for user_id, lang in recipients:
        text = _MESSAGES.get(lang, _MESSAGES["en"])
        try:
            if promo_bytes is not None:
                if promo_file_id is not None:
                    photo = promo_file_id
                else:
                    photo = io.BytesIO(promo_bytes)
                    photo.name = "promo.png"
                msg = await bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                    write_timeout=120,
                    read_timeout=60,
                    connect_timeout=30,
                )
                if promo_file_id is None and msg.photo:
                    promo_file_id = msg.photo[-1].file_id
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            sent += 1
        except Exception as e:  # blocked the bot, deactivated account, etc.
            failed += 1
            logger.debug("Could not message %s: %s", user_id, e)

        # Gentle pacing to stay within Telegram's ~30 msg/sec broadcast limit.
        await asyncio.sleep(0.05)

    # Mark done so the grant/broadcast never repeats.
    await set_setting(_FLAG_KEY, "done")
    logger.info(
        "✅ Image-feature broadcast complete — sent: %d, failed: %d. Flag '%s' set.",
        sent, failed, _FLAG_KEY,
    )
