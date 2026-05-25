import json
import logging
import re

from llm import gemini_client

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a grammar teacher for learners of English and Japanese.
The user is asking a question about a grammar pattern. Your job:

1. Identify the grammar pattern they're asking about.
2. Determine the language of that pattern (English or Japanese) → target_lang.
3. Determine the language to explain it in (explanation_lang). Rule:
   - If the question text (outside the grammar pattern itself) is mostly in one language,
     use that language for the explanation.
   - Otherwise, default to the language opposite to target_lang.

Return a JSON object with this exact structure:

{
  "topic": "the grammar pattern, e.g. '〜てしまう' or 'would have p.p.'",
  "target_lang": "en" or "ja",
  "explanation_lang": "en" or "ja",
  "explanation": "clear explanation in explanation_lang (keep under ~600 characters)",
  "examples": [
    {"source": "an example using the pattern", "translation": "translation in explanation_lang"}
  ],
  "related": "related grammar notes in explanation_lang (under ~200 chars, or empty string)"
}

Provide 2-3 examples. Respond ONLY with the JSON object, no markdown fences, no extra text."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


async def handle_grammar(text: str) -> dict:
    raw_response = await gemini_client.generate(_SYSTEM_PROMPT, text)
    cleaned = _strip_code_fences(raw_response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e

    return {
        "topic": parsed["topic"],
        "target_lang": parsed["target_lang"],
        "explanation_lang": parsed["explanation_lang"],
        "explanation": parsed["explanation"],
        "examples": parsed.get("examples", []),
        "related": parsed.get("related", ""),
    }
