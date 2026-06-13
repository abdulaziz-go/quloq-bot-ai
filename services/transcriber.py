"""
services/transcriber.py — Audio transcription via Google Gemini.

Passes audio as inline bytes directly to generate_content — no Files API.
This avoids the Files API upload endpoint which is unreliable from some regions.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

# 120 s HTTP-level timeout covers slow inference on long audio
_client = genai.Client(
    api_key=config.google_api_key,
    http_options=types.HttpOptions(timeout=120_000),
)

MAX_INLINE_AUDIO_BYTES = 20 * 1024 * 1024  # 20 MB — Gemini inline data limit

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0
_RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


def _error_status(exc: Exception) -> int | None:
    for attr in ("code", "status_code", "http_status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    return None


async def _with_retry(coro_factory, label: str):
    """Run an async operation with exponential backoff on transient errors.

    Retries on asyncio.TimeoutError and ServerError with 5xx status codes.
    Raises immediately on 4xx errors (auth, bad request, etc.).
    """
    delay = _RETRY_BASE_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except asyncio.TimeoutError:
            if attempt == _MAX_RETRIES:
                logger.error("%s timed out after %d attempts.", label, attempt)
                raise
            logger.warning(
                "%s timed out (attempt %d/%d), retrying in %.0fs…",
                label, attempt, _MAX_RETRIES, delay,
            )
        except genai_errors.ServerError as exc:
            code = _error_status(exc)
            if code not in _RETRYABLE_STATUS_CODES:
                raise
            if attempt == _MAX_RETRIES:
                logger.error(
                    "%s server error %s after %d attempts: %s", label, code, attempt, exc
                )
                raise
            logger.warning(
                "%s server error %s (attempt %d/%d), retrying in %.0fs…",
                label, code, attempt, _MAX_RETRIES, delay,
            )
        await asyncio.sleep(delay)
        delay *= 2


# MIME type mapping by extension
_MIME_TYPES: dict[str, str] = {
    ".ogg":  "audio/ogg",
    ".mp3":  "audio/mpeg",
    ".mp4":  "video/mp4",
    ".m4a":  "audio/mp4",
    ".wav":  "audio/wav",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
    ".oga":  "audio/ogg",
}

_TRANSCRIBE_PROMPT = """\
You are a strict, literal speech-to-text transcriber. Write down EXACTLY what is spoken in the audio — nothing more, nothing less.

═══ ABSOLUTE RULES (these override everything else) ═══
1. Transcribe ONLY words that are actually and clearly spoken in THIS audio.
2. NEVER invent, guess, complete, predict, or "improve" words. If a word is unclear, write only the part you can clearly hear and nothing else.
3. NEVER add anything that was not spoken — no greetings, no goodbyes, no "thank you", no titles, no commentary, no filler you did not actually hear.
4. Do NOT paraphrase, do NOT summarize, do NOT translate, do NOT correct grammar, do NOT change word order.
5. If the audio is silent, contains only background noise or music, or is completely unintelligible, return an EMPTY string "" for "text". Never fill an empty/unclear recording with made-up content.
6. Do NOT repeat words or phrases more times than they are actually said.

═══ FAITHFULNESS TO THE SPEAKER ═══
- Keep filler words, hesitations, false starts, and repetitions exactly as spoken.
- Keep colloquial and non-standard pronunciations exactly as heard — do NOT normalize them to standard/literary forms.
- Keep code-switched words (e.g. Russian words inside Uzbek speech) in their spoken form, written in the script of the surrounding language.

═══ PUNCTUATION (formatting only — must NEVER change or add words) ═══
- Add basic sentence punctuation (. ? !) and commas at natural pauses.
- Capitalize the first letter of each sentence.
- Split long speech into paragraphs using \\n\\n at clear topic shifts or long pauses.

═══ OUTPUT ═══
Return ONLY a valid JSON object, with no markdown fences and no explanation:
{
  "text": "<verbatim transcription, or \\"\\" if nothing intelligible is spoken>",
  "language": "<detected spoken language in English, e.g. English, Russian, Uzbek; \\"\\" if no speech>"
}
"""


@dataclass
class TranscriptResult:
    text: str
    language: str | None
    duration_sec: float | None
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def _get_mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return _MIME_TYPES.get(ext, "audio/ogg")


def _transcribe_sync(audio_bytes: bytes, mime: str):
    """Synchronous generate_content call — wrapped via asyncio.to_thread."""
    return _client.models.generate_content(
        model=config.audio_model,
        contents=[
            _TRANSCRIBE_PROMPT,
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            # Deterministic, non-creative decoding — the single biggest lever
            # against the model inventing words that were never spoken.
            temperature=0.0,
            top_p=1.0,
            top_k=1,
        ),
    )


async def transcribe_telegram_file(
    tg_file,
    file_name: str = "audio.ogg",
    duration_sec: float | None = None,
) -> TranscriptResult:
    """
    Download a Telegram audio file and transcribe it via Gemini.
    Returns TranscriptResult with verbatim text and detected language.
    """
    logger.info("Downloading '%s' for transcription…", file_name)

    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    audio_bytes = buf.getvalue()

    size_kb = len(audio_bytes) / 1024
    if len(audio_bytes) > MAX_INLINE_AUDIO_BYTES:
        raise ValueError(
            f"Audio file too large for inline transcription: {size_kb:.0f} KB "
            f"(limit {MAX_INLINE_AUDIO_BYTES // 1024} KB)"
        )

    mime = _get_mime(file_name)
    logger.info("Transcribing %.1f KB inline (mime=%s)…", size_kb, mime)

    response_text = ""
    tokens = 0
    input_tokens = 0
    output_tokens = 0

    try:
        response = await _with_retry(
            lambda: asyncio.wait_for(
                asyncio.to_thread(_transcribe_sync, audio_bytes, mime),
                timeout=120.0,
            ),
            "generate_content",
        )

        text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
        response_text = "".join(text_parts).strip()

        if response.usage_metadata:
            tokens = response.usage_metadata.total_token_count
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count

        # Strip markdown fences if the model wrapped the JSON
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()
            response_text = response_text.strip("`").strip()

        data = json.loads(response_text)
        text: str = data.get("text", "").strip()
        language: str | None = data.get("language")

    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("JSON parse failed (%s), using raw response as text.", exc)
        text = response_text
        language = None

    except Exception as exc:
        logger.exception("Transcription error: %s", exc)
        raise

    logger.info(
        "Transcription done. Language=%s  Duration=%.1fs  Chars=%d Tokens=%d",
        language, duration_sec or 0, len(text), tokens,
    )

    return TranscriptResult(
        text=text,
        language=language,
        duration_sec=duration_sec,
        tokens=tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )