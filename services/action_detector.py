"""services/action_detector.py — Smart action extraction via Google Gemini (google-genai SDK)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=config.google_api_key)

_SYSTEM = """\
You are an expert at extracting structured action items from voice message transcripts.

Analyse the transcript and extract:
1. tasks     — concrete things someone needs to do
2. deadlines — specific dates, times, or time references tied to actions
3. questions — open questions that need answers

Return ONLY valid JSON in this exact schema:
{
  "tasks": ["string", ...],
  "deadlines": ["string", ...],
  "questions": ["string", ...]
}

Rules:
- Each item must be a short, self-contained statement.
- If a category has no items, return an empty array [].
- Do NOT include vague or filler items.
- Match the language of the transcript if it is not English.
"""


@dataclass
class ActionItems:
    tasks: list[str] = field(default_factory=list)
    deadlines: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.tasks or self.deadlines or self.questions)

    @property
    def total_count(self) -> int:
        return len(self.tasks) + len(self.deadlines) + len(self.questions)


async def extract_actions(transcript: str) -> ActionItems:
    """Extract tasks, deadlines, and questions from a transcript using Gemini."""
    logger.info("Extracting actions from %d-char transcript…", len(transcript))

    response = await _client.aio.models.generate_content(
        model=config.gemini_model,
        contents=transcript,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0.2,
            max_output_tokens=500,
            response_mime_type="application/json",
        ),
    )

    # Extract text parts manually to avoid warnings about non-text parts (like thought_signature)
    text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
    response_text = "".join(text_parts).strip() if text_parts else ""
    
    tokens = 0
    input_tokens = 0
    output_tokens = 0
    if response.usage_metadata:
        tokens = response.usage_metadata.total_token_count
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count

    # Robust JSON cleaning
    if "```" in response_text:
        parts = response_text.split("```")
        for p in parts:
            if "{" in p and "}" in p:
                response_text = p.strip()
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()
                break

    try:
        data = json.loads(response_text)
        result = ActionItems(
            tasks=data.get("tasks", []),
            deadlines=data.get("deadlines", []),
            questions=data.get("questions", []),
            tokens=tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Failed to parse action JSON: %s", exc)
        result = ActionItems(tokens=tokens, input_tokens=input_tokens, output_tokens=output_tokens)

    logger.info(
        "Extracted %d tasks, %d deadlines, %d questions. Tokens=%d",
        len(result.tasks), len(result.deadlines), len(result.questions), tokens
    )
    return result
