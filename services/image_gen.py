"""
services/image_gen.py — AI image generation via Google Gemini "Nano Banana".

Uses the gemini-2.5-flash-image model (codename "Nano Banana") to turn a text
prompt into an image. Returns raw PNG/JPEG bytes ready to send via Telegram.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

# 120 s HTTP-level timeout covers slow image inference.
_client = genai.Client(
    api_key=config.google_api_key,
    http_options=types.HttpOptions(timeout=120_000),
)

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
    """Run an async operation with exponential backoff on transient 5xx/timeout errors."""
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
                logger.error("%s server error %s after %d attempts: %s", label, code, attempt, exc)
                raise
            logger.warning(
                "%s server error %s (attempt %d/%d), retrying in %.0fs…",
                label, code, attempt, _MAX_RETRIES, delay,
            )
        await asyncio.sleep(delay)
        delay *= 2


@dataclass
class ImageResult:
    image_bytes: bytes
    mime_type: str
    caption: str | None  # any text the model returned alongside the image
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def _generate_sync(prompt: str):
    """Synchronous text→image generate_content call — wrapped via asyncio.to_thread."""
    return _client.models.generate_content(
        model=config.image_model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["Text", "Image"],
        ),
    )


def _edit_sync(image_bytes: bytes, mime: str, prompt: str):
    """Synchronous image+text→image generate_content call — wrapped via asyncio.to_thread."""
    return _client.models.generate_content(
        model=config.image_model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["Text", "Image"],
        ),
    )


def _extract_image(response) -> ImageResult:
    """Pull the first image part (and any text) out of a Gemini response.

    Raises RuntimeError if the model returned no image (e.g. a safety refusal).
    """
    image_bytes: bytes | None = None
    mime_type = "image/png"
    text_chunks: list[str] = []

    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/png"
        elif getattr(part, "text", None):
            text_chunks.append(part.text)

    if not image_bytes:
        # No image part — usually a safety refusal; surface any text the model gave.
        refusal = " ".join(text_chunks).strip()
        logger.warning("Image response had no image. Model text: %s", refusal[:200])
        raise RuntimeError(refusal or "No image generated")

    tokens = input_tokens = output_tokens = 0
    if response.usage_metadata:
        tokens = response.usage_metadata.total_token_count or 0
        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0

    caption = " ".join(text_chunks).strip() or None
    logger.info("Image ready (%d bytes, mime=%s, %d tokens).", len(image_bytes), mime_type, tokens)

    return ImageResult(
        image_bytes=image_bytes,
        mime_type=mime_type,
        caption=caption,
        tokens=tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def generate_image(prompt: str) -> ImageResult:
    """
    Generate an image from a text prompt using Gemini "Nano Banana".
    Raises RuntimeError if the model returns no image (e.g. safety filter).
    """
    logger.info("Generating image for prompt (%d chars)…", len(prompt))

    response = await _with_retry(
        lambda: asyncio.wait_for(
            asyncio.to_thread(_generate_sync, prompt),
            timeout=120.0,
        ),
        "generate_image",
    )
    return _extract_image(response)


async def edit_image(image_bytes: bytes, mime: str, prompt: str) -> ImageResult:
    """
    Edit/transform an existing image according to a text instruction, using
    Gemini "Nano Banana". Returns the new image bytes.
    Raises RuntimeError if the model returns no image (e.g. safety filter).
    """
    logger.info("Editing image (%d bytes, mime=%s) with instruction (%d chars)…",
                len(image_bytes), mime, len(prompt))

    response = await _with_retry(
        lambda: asyncio.wait_for(
            asyncio.to_thread(_edit_sync, image_bytes, mime, prompt),
            timeout=120.0,
        ),
        "edit_image",
    )
    return _extract_image(response)
