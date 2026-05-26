import json
import logging
import re
from urllib.parse import quote

from llm import gemini_client

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    reading_rule = (
        '\n  "reading": "hiragana reading of the headword if it contains kanji; empty string otherwise (already hiragana/katakana, or non-Japanese)",'
        if target_lang == "ja"
        else ""
    )
    return f"""You are a {target_name} language teacher for {explanation_name} speakers.

The user submits a single word or short phrase. It may be either:
  (a) in {target_name} — the language they are studying, or
  (b) in {explanation_name} — their native language, asking for the {target_name} equivalent.

If (a), use the submitted word as the headword.
If (b), pick the single most natural {target_name} equivalent and use THAT as the headword.

Then return a JSON object with this exact structure:

{{
  "headword": "the {target_name} word/phrase that serves as the main entry (always in {target_name})",{reading_rule}
  "translation": "translation of the headword in {explanation_name}",
  "part_of_speech": "noun / verb / adjective / etc.",
  "meaning": "brief meaning in {explanation_name}, written for an early-stage learner (simple wording, no jargon)",
  "usage": "1-2 short notes about usage or collocations in {explanation_name}",
  "examples": [
    {{"source": "example sentence in {target_name}", "translation": "translation in {explanation_name}"}},
    {{"source": "another example", "translation": "translation"}}
  ]
}}

Provide 2 example sentences. The `source` of each example must be in {target_name}.
Respond ONLY with the JSON object, no extra text, no markdown fences."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _build_dictionary_url(word: str, template: str) -> str:
    return template.format(word=quote(word))


async def handle_word(
    word: str,
    target_lang: str,
    explanation_lang: str,
    dictionary_url_template: str,
) -> dict:
    system_prompt = _build_system_prompt(target_lang, explanation_lang)
    raw_response = await gemini_client.generate(system_prompt, word)
    cleaned = _strip_code_fences(raw_response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e

    headword = parsed["headword"]
    return {
        "word": headword,
        "reading": parsed.get("reading", ""),
        "translation": parsed["translation"],
        "part_of_speech": parsed["part_of_speech"],
        "meaning": parsed["meaning"],
        "usage": parsed["usage"],
        "examples": parsed["examples"],
        "dictionary_url": _build_dictionary_url(headword, dictionary_url_template),
    }
