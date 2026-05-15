"""services/translator.py — Voice message translation via Google Gemini."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=config.google_api_key)

_SYSTEM = (
    "You are a professional translator for voice message transcripts.\n\n"
    "Rules:\n"
    "- Translate the given text accurately to the target language: {target_lang}.\n"
    "- Preserve the original tone and any key names or numbers.\n"
    "- If the text is already in the target language, return it as is.\n"
    "- Reply ONLY with the translated text — no preamble, no explanations."
)


async def translate_text(text: str, target_lang: str) -> tuple[str, int]:
    """Translate transcript to English, Russian, or Uzbek using Gemini."""
    logger.info("Translating %d-char text to %s…", len(text), target_lang)

    # Convert language code to full name for AI
    lang_names = {"uz": "Uzbek", "ru": "Russian", "en": "English"}
    full_lang = lang_names.get(target_lang, "English")

    response = await _client.aio.models.generate_content(
        model=config.gemini_model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM.format(target_lang=full_lang),
            temperature=0.3,
            max_output_tokens=1000,
        ),
    )

    # Extract text parts manually to avoid warnings about non-text parts (like thought_signature)
    text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
    translation = "".join(text_parts).strip() if text_parts else "Failed to generate translation due to API filter."
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
    logger.info("Translation complete (%d chars, %d tokens).", len(translation), tokens)
    return translation, tokens
