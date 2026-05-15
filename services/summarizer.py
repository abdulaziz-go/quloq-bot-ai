"""services/summarizer.py — Concise summarization via Google Gemini (google-genai SDK)."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=config.google_api_key)

_SYSTEM = (
    "You are a precise and concise summarizer for voice message transcripts.\n\n"
    "Rules:\n"
    f"- Write a clear, flowing summary in plain prose (no bullet points).\n"
    f"- Maximum {config.summary_max_sentences} sentences.\n"
    "- Preserve key intent, decisions, names, and numbers.\n"
    "- If the transcript is very short (< 30 words), respond with:\n"
    '  "This message is too short to summarize."\n'
    "- Reply ONLY with the summary — no preamble, no labels.\n"
    "- Match the language of the transcript if it is not English."
)


async def summarize(transcript: str) -> tuple[str, int]:
    """Return a tuple of (summary_text, total_tokens)."""
    logger.info("Generating summary for %d-char transcript…", len(transcript))

    response = await _client.aio.models.generate_content(
        model=config.gemini_model,
        contents=transcript,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0.3,
            max_output_tokens=300,
        ),
    )

    # Extract text parts manually to avoid warnings about non-text parts (like thought_signature)
    text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
    summary = "".join(text_parts).strip() if text_parts else "Failed to generate summary due to API filter."
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
    
    logger.info("Summary generated (%d chars, %d tokens).", len(summary), tokens)
    return summary, tokens
