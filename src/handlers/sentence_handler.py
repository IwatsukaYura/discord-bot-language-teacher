import json
import logging
import re

from llm import gemini_client
from llm.persona import GRIZZO_PERSONA_BLOCK

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    task_block = f"""Your task: translate a {target_name} sentence for {explanation_name} speakers.
Return a JSON object with this exact structure:

{{
  "translation": "natural translation in {explanation_name} — neutral tone, no character voice",
  "literal_translation": "more literal translation in {explanation_name} for understanding nuance (empty string if unnecessary) — neutral tone, no character voice",
  "key_points": [
    "brief note about an important expression or grammar in {explanation_name} — neutral reference-book tone, no character voice (no 〜だよ / 〜だね / 一人称)",
    "another note"
  ],
  "grizzo_comment": "ぐりぞー's short in-character reaction to this specific sentence, in {explanation_name}, following the persona rules above"
}}

Provide 1-3 key points only when they would meaningfully help the learner. An empty array is OK.
Respond ONLY with the JSON object, no markdown fences, no extra text."""
    return f"{GRIZZO_PERSONA_BLOCK}\n\n{task_block}"


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


async def handle_sentence(
    text: str,
    target_lang: str,
    explanation_lang: str,
) -> dict:
    system_prompt = _build_system_prompt(target_lang, explanation_lang)
    raw_response = await gemini_client.generate(system_prompt, text)
    cleaned = _strip_code_fences(raw_response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e

    return {
        "source_text": text,
        "translation": parsed["translation"],
        "literal_translation": parsed.get("literal_translation", ""),
        "key_points": parsed.get("key_points", []),
        "grizzo_comment": parsed.get("grizzo_comment", ""),
    }
