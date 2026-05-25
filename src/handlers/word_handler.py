import json
import logging
import re
from urllib.parse import quote

from llm import gemini_client
from llm.persona import GRIZZO_PERSONA_BLOCK

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    reading_field = (
        '\n  "reading": "hiragana reading of the word if it contains kanji; empty string if the word has no kanji (e.g. already hiragana, katakana, or non-Japanese)",'
        if target_lang == "ja"
        else ""
    )
    task_block = f"""Your task: explain a single {target_name} word for {explanation_name} speakers.
Return a JSON object with this exact structure:

{{
  "translation": "translation in {explanation_name} — neutral reference tone, no character voice",{reading_field}
  "part_of_speech": "noun / verb / adjective / etc.",
  "meaning": "brief meaning in {explanation_name} — neutral reference-book tone, no character voice (no 〜だよ / 〜だね / 一人称)",
  "usage": "1-2 short notes about usage or collocations in {explanation_name} — neutral reference-book tone, no character voice (no 〜だよ / 〜だね / 一人称)",
  "examples": [
    {{"source": "example sentence in {target_name}", "translation": "translation in {explanation_name} — neutral tone"}},
    {{"source": "another example", "translation": "translation — neutral tone"}}
  ],
  "grizzo_comment": "ぐりぞー's short in-character reaction to this specific word, in {explanation_name}, following the persona rules above"
}}

Provide 2 example sentences. Respond ONLY with the JSON object, no extra text, no markdown fences."""
    return f"{GRIZZO_PERSONA_BLOCK}\n\n{task_block}"


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

    return {
        "word": word,
        "reading": parsed.get("reading", ""),
        "translation": parsed["translation"],
        "part_of_speech": parsed["part_of_speech"],
        "meaning": parsed["meaning"],
        "usage": parsed["usage"],
        "examples": parsed["examples"],
        "grizzo_comment": parsed.get("grizzo_comment", ""),
        "dictionary_url": _build_dictionary_url(word, dictionary_url_template),
    }
