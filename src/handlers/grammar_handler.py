import json
import logging
import re

from llm import gemini_client

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    return f"""You are a {target_name} grammar teacher for {explanation_name} speakers.
The user is asking a question about a {target_name} grammar pattern. Your job is
to identify the pattern and explain it in {explanation_name}.

Return a JSON object with this exact structure:

{{
  "topic": "the grammar pattern, e.g. '〜てしまう' or 'would have p.p.'",
  "explanation": "clear explanation in {explanation_name} (keep under ~600 characters). Assume an early-stage learner; keep the wording simple and avoid jargon.",
  "examples": [
    {{"source": "a {target_name} example using the pattern", "translation": "translation in {explanation_name}"}}
  ],
  "related": "related grammar notes in {explanation_name} (under ~200 chars, or empty string)"
}}

Provide 2-3 examples. Respond ONLY with the JSON object, no markdown fences, no extra text."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


async def handle_grammar(text: str, target_lang: str, explanation_lang: str) -> dict:
    system_prompt = _build_system_prompt(target_lang, explanation_lang)
    raw_response = await gemini_client.generate(system_prompt, text)
    cleaned = _strip_code_fences(raw_response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e

    return {
        "topic": parsed["topic"],
        "target_lang": target_lang,
        "explanation_lang": explanation_lang,
        "explanation": parsed["explanation"],
        "examples": parsed.get("examples", []),
        "related": parsed.get("related", ""),
    }
