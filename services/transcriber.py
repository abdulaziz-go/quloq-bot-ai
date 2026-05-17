"""
services/transcriber.py — Audio transcription via Google Gemini 2.0 Flash.

Uses the official `google-genai` SDK (not the deprecated google-generativeai).
Gemini 2.0 Flash natively understands audio — transcribes + detects language in one call.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

# Shared async client
_client = genai.Client(api_key=config.google_api_key)

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
Transcribe the audio message verbatim. Every word the speaker says must appear — no paraphrasing, no omissions, no "cleaning up" of speech.

PRESERVE SPOKEN STYLE:
- Keep ALL filler words and discourse markers exactly as spoken (e.g., "koroche", "prosto", "lish", "kak", "no", "nu", "vot", "haligi", "yani"). Do NOT drop them, do NOT normalize them to literary forms.
- Keep colloquial/spoken pronunciations as the speaker said them (e.g., "to'g'irlashim" not "to'g'rilashim" if that is what was said; "prosto" not "prosta"; "bo'laverardi" not "bo'laveradi"). Match what you actually hear.
- Keep code-switched words (Russian inside Uzbek, etc.) in their spoken form. Transliterate Russian words into Latin script using the same script as the surrounding language.
- Do NOT add words. Do NOT rephrase. Do NOT summarize. Do NOT correct grammar.

PUNCTUATION & FORMATTING:
- Add sentence-ending punctuation (. ? !) at natural sentence boundaries.
- Add commas at natural pauses and clause boundaries.
- Capitalize the first letter of each sentence.
- Use guillemets «» around speech the speaker is quoting from themselves or others (e.g., «Oldingidek vnimaniya qiling»). Use regular quotes "" only if guillemets are not appropriate for the language.
- Use an em-dash or hyphen-connector where the speaker chains clauses tightly (e.g., "aytyapman-u", "kerak-ku").
- Break the transcription into PARAGRAPHS at natural topic shifts or long pauses. Do NOT return one giant wall of text — a 30+ second monologue should typically be 2–4 paragraphs.

OUTPUT:
Return ONLY a valid JSON object with exactly these two fields, no markdown fences, no explanation:
{
  "text": "<full verbatim transcription with punctuation and paragraph breaks>",
  "language": "<detected language in English, e.g. English, Russian, Uzbek, Arabic>"
}

In the JSON string, represent paragraph breaks as \\n\\n (two newline characters).
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


def _upload_sync(tmp_path: str, mime_type: str):
    """Synchronous upload — wrapped via asyncio.to_thread."""
    with open(tmp_path, "rb") as f:
        return _client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type=mime_type),
        )


def _get_file_sync(file_name: str):
    """Synchronous file state fetch — wrapped via asyncio.to_thread."""
    return _client.files.get(name=file_name)


def _delete_sync(file_name: str) -> None:
    """Synchronous delete — wrapped via asyncio.to_thread."""
    try:
        _client.files.delete(name=file_name)
    except Exception as exc:
        logger.warning("Could not delete Gemini file %s: %s", file_name, exc)


async def _wait_for_active(file_name: str, max_wait: float = 60.0) -> None:
    """Poll until the Gemini file reaches ACTIVE state (needed for video files)."""
    deadline = asyncio.get_event_loop().time() + max_wait
    while asyncio.get_event_loop().time() < deadline:
        info = await asyncio.to_thread(_get_file_sync, file_name)
        state = getattr(info, "state", None)
        state_name = state.name if state else str(state)
        if state_name == "ACTIVE":
            logger.debug("Gemini file %s is ACTIVE.", file_name)
            return
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed for {file_name}.")
        logger.debug("Gemini file %s state=%s — waiting…", file_name, state_name)
        await asyncio.sleep(2)
    raise TimeoutError(f"Gemini file {file_name} did not become ACTIVE within {max_wait}s.")


async def transcribe_telegram_file(
    tg_file,
    file_name: str = "audio.ogg",
    duration_sec: float | None = None,
) -> TranscriptResult:
    """
    Download a Telegram audio file and transcribe it via Gemini 2.0 Flash.
    Returns TranscriptResult with verbatim text and detected language.
    """
    logger.info("Downloading '%s' for transcription…", file_name)

    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    buf.seek(0)

    suffix = Path(file_name).suffix or ".ogg"
    mime = _get_mime(file_name)

    tmp_path = None
    gemini_file = None
    response_text = ""
    tokens = 0

    try:
        # Write to temp file (Files API needs a path)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name

        size_kb = os.path.getsize(tmp_path) / 1024
        logger.info("Uploading %.1f KB to Gemini Files API (mime=%s)…", size_kb, mime)

        gemini_file = await asyncio.to_thread(_upload_sync, tmp_path, mime)

        # Video files need processing time before they become ACTIVE
        await _wait_for_active(gemini_file.name)

        response = await _client.aio.models.generate_content(
            model=config.audio_model,
            contents=[
                types.Part.from_uri(
                    file_uri=gemini_file.uri,
                    mime_type=mime,
                ),
                _TRANSCRIBE_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )

        # Extract text manually to avoid warnings about non-text parts (like thought_signature)
        text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
        response_text = "".join(text_parts).strip()
        tokens = 0
        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            tokens = response.usage_metadata.total_token_count
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count

        # Clean up any markdown blocks if they exist
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

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if gemini_file:
            await asyncio.to_thread(_delete_sync, gemini_file.name)

    logger.info(
        "Transcription done. Language=%s  Duration=%.1fs  Chars=%d Tokens=%d",
        language, duration_sec or 0, len(text), tokens
    )

    return TranscriptResult(
        text=text,
        language=language,
        duration_sec=duration_sec,
        tokens=tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens
    )
