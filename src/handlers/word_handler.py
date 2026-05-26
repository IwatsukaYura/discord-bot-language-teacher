import json
import logging
import re
from urllib.parse import quote

from llm import gemini_client

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    is_ja_target = target_lang == "ja"

    word_reading_field = (
        '\n  "reading": "hiragana reading of the headword if it contains kanji; empty string otherwise",'
        if is_ja_target
        else '\n  "reading": "",'
    )

    if is_ja_target:
        translation_reading_rule = (
            "- For each translation entry, set `reading` to the hiragana reading of `text` when `text` contains kanji. "
            "If `text` has no kanji (already hiragana / katakana / non-Japanese), set `reading` to an empty string."
        )
    else:
        translation_reading_rule = (
            "- All translation `reading` fields MUST be empty strings "
            "(the learner is a Japanese native speaker who does not need furigana)."
        )

    return f"""You are a {target_name} dictionary teacher for {explanation_name} speakers.

The user submits a single word or short phrase. It may be either:
  (a) in {target_name} — the language they are studying, or
  (b) in {explanation_name} — their native language, asking for the {target_name} equivalent.

If (a), use the submitted word as the headword.
If (b), pick the single most natural {target_name} equivalent and use THAT as the headword.

If the word has SEVERAL distinct meanings that a learner would meaningfully benefit from knowing,
split them into 2-3 separate sense entries. If it has only one main meaning, return ONE sense.
Do NOT pad with niche or rare meanings just to fill the array.

Return a JSON object with this exact structure:

{{
  "headword": "the {target_name} word/phrase that serves as the main entry (always in {target_name})",{word_reading_field}
  "part_of_speech": "noun / verb / adjective / etc.",
  "senses": [
    {{
      "translations": [
        {{"text": "one {explanation_name} translation word/phrase", "reading": ""}}
      ],
      "meaning": "brief meaning in {explanation_name}, written for an early-stage learner (simple wording, no jargon)",
      "usage": "1-2 short notes about usage or collocations in {explanation_name}",
      "examples": [
        {{"source": "natural example sentence in {target_name}", "translation": "translation in {explanation_name}"}}
      ]
    }}
  ]
}}

Rules:
- Provide exactly 2 example sentences per sense.
- Every example's `translation` field MUST contain the user's submitted form OR its inflection / part-of-speech variant. For example, if the user submitted "retrieval", every example translation must contain one of: retrieval, retrieve, retrieved, retrieves, retrieving. Do NOT substitute with a synonym like "search" or "look up" in place of the user's word.
- Each `translations[].text` is a SINGLE word or short phrase. Do not pack multiple alternatives into one string (e.g. "search / retrieval"); list them as separate entries in the `translations` array.
- Provide 1-3 translation entries per sense, ordered by typicality.
{translation_reading_rule}
- `meaning` and `usage` are written in {explanation_name}.

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
        "part_of_speech": parsed["part_of_speech"],
        "senses": parsed["senses"],
        "dictionary_url": _build_dictionary_url(headword, dictionary_url_template),
    }
