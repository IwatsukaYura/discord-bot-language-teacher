import json
import logging
import re
from urllib.parse import quote

from llm import client as llm_client

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

The user submits a single word or short phrase. FIRST decide which mode applies based on the language of the submitted word.

MODE A — DIRECT LOOKUP (the submitted word IS a {target_name} word)
  - ALL senses share the SAME `headword`, equal to the user's submitted word (normalized to a base/dictionary form if needed).
  - Senses differ by MEANING. Split into separate senses when the word maps to substantially different {explanation_name} translations.
  - Example: "retrieval" → sense 1: translations=["検索", "取り出し"] (data context); sense 2: translations=["回収"] (physical recovery). These ARE different enough.
  - Example: "bank" → sense 1: translations=["銀行"]; sense 2: translations=["土手", "川岸"].
  - Combine into ONE sense only when meanings genuinely overlap (e.g. "apple" has one common meaning).
  - `examples[].source` is a natural {target_name} sentence that contains the headword.
  - `examples[].translation` is a natural {explanation_name} translation. Do NOT inject the {target_name} word; write naturally.

MODE B — REVERSE LOOKUP (the submitted word is a {explanation_name} word, asking for the {target_name} equivalent)
  - Each sense has its OWN distinct {target_name} `headword`.
  - `translations` lists the {explanation_name} words corresponding to that sense's headword. Typically includes the user's submitted word plus near-synonyms.
  - Example: user submits "retrieval" (English), target is Japanese → sense 1: headword="検索", translations=["search", "retrieval", "lookup"]; sense 2: headword="回収", translations=["recovery", "collection"].
  - `examples[].source` is a natural {target_name} sentence containing that sense's headword.
  - `examples[].translation` is a natural {explanation_name} sentence that MUST contain the user's submitted form (or its inflection).

How to decide the mode:
- If the submitted word's primary language is {target_name}, use MODE A.
- If it's {explanation_name}, use MODE B.
- For ambiguous loanwords / proper nouns, prefer MODE A.

Common rules:
- Provide 1-3 senses. If the word has only one main meaning, return ONE sense. Do NOT pad with niche meanings.
- Provide exactly 2 examples per sense.
- `translations` is a list of 1-3 short {explanation_name} words/phrases (NOT full sentences). Order by typicality.
{headword_reading_rule}

Return a JSON object with this exact structure:

{{
  "input": "the exact word/phrase the user submitted (echo back verbatim)",
  "mode": "A" or "B",
  "senses": [
    {{
      "headword": "see mode rules above (always in {target_name})",{headword_reading_field}
      "part_of_speech": "noun / verb / adjective / etc.",
      "translations": ["one {explanation_name} word/phrase", "another"],
      "examples": [
        {{"source": "natural {target_name} sentence", "translation": "natural {explanation_name} translation"}}
      ]
    }}
  ]
}}

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
    result = await llm_client.generate(system_prompt, word)
    cleaned = _strip_code_fences(result.text)

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
        "model_label": llm_client.format_model(result),
    }
