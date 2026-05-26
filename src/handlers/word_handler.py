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

    if is_ja_target:
        headword_reading_field = (
            '\n      "headword_reading": "hiragana reading of the headword if it contains kanji; empty string otherwise",'
        )
        headword_reading_rule = (
            "- Each sense's `headword_reading` is the hiragana reading of `headword` when `headword` contains kanji. "
            "Empty string when there is no kanji (already hiragana / katakana / non-Japanese)."
        )
    else:
        headword_reading_field = '\n      "headword_reading": "",'
        headword_reading_rule = (
            "- All `headword_reading` fields MUST be empty strings "
            "(the learner is a Japanese native speaker and does not need furigana)."
        )

    return f"""You are a {target_name} dictionary teacher for {explanation_name} speakers.

The user submits a single word or short phrase. It may be either:
  (a) in {target_name} — the language they are studying, or
  (b) in {explanation_name} — their native language, asking for the {target_name} equivalent.

Identify the distinct major senses of the user's input as expressed in {target_name}.
EACH SENSE GETS ITS OWN {target_name} HEADWORD and its own examples.

For example, if the user submits "retrieval" (English) and the bot teaches Japanese,
plausible senses are: 検索 (looking up info), 取り出し (extracting), 回収 (recovering a lost item),
回復 (restoring). Pick 1-3 of the most useful for the learner.

If the word has only ONE main meaning, return ONE sense. Do NOT pad with niche meanings.

Return a JSON object with this exact structure:

{{
  "input": "the exact word/phrase the user submitted (echo back verbatim)",
  "senses": [
    {{
      "headword": "the {target_name} headword for this sense (always in {target_name})",{headword_reading_field}
      "part_of_speech": "noun / verb / adjective / etc.",
      "meaning": "brief meaning in {explanation_name}, written for an early-stage learner (simple wording, no jargon)",
      "usage": "1-2 short notes about usage or collocations in {explanation_name}",
      "examples": [
        {{"source": "natural {target_name} sentence containing the sense's headword", "translation": "translation in {explanation_name} containing the user's submitted word (or its inflection)"}}
      ]
    }}
  ]
}}

Rules:
- Provide exactly 2 examples per sense.
- Each example's `source` MUST contain the SAME sense's headword (or its inflection / part-of-speech variant).
- Each example's `translation` MUST contain the user's submitted form OR its inflection / part-of-speech variant. For example, if the user submitted "retrieval", every example translation must contain one of: retrieval, retrieve, retrieved, retrieves, retrieving.
- The two examples in a sense should use the SAME sense's headword consistently (do not switch headwords mid-sense).
{headword_reading_rule}
- `meaning` and `usage` are in {explanation_name}.

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

    user_input = parsed.get("input", word)
    return {
        "input": user_input,
        "senses": parsed["senses"],
        "dictionary_url": _build_dictionary_url(user_input, dictionary_url_template),
    }
