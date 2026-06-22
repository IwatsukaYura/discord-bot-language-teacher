import logging

from lib.lang import lang_names
from llm import client as llm_client
from llm.parsing import parse_json_response

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name, explanation_name = lang_names(target_lang, explanation_lang)
    reading_rule = (
        '\n  "source_reading": "hiragana reading of source_text for any kanji it contains; empty string if no kanji",'
        if target_lang == "ja"
        else ""
    )
    return f"""You are a {target_name} sentence teacher for {explanation_name} speakers.

The user submits a sentence. It may be either:
  (a) in {target_name} — the language they are studying, or
  (b) in {explanation_name} — their native language, asking how to say it in {target_name}.

If (a), use the user's sentence as `source_text`.
If (b), translate it into natural {target_name} and use THAT as `source_text`.

Return a JSON object with this exact structure:

{{
  "source_text": "the {target_name} sentence (see rule above)",{reading_rule}
  "translation": "natural translation in {explanation_name}",
  "literal_translation": "more literal translation in {explanation_name} for nuance (empty string if unnecessary)",
  "key_points": [
    "brief note about an important expression or grammar in {explanation_name}, written simply for an early-stage learner",
    "another note"
  ]
}}

Provide 1-3 key points only when they would meaningfully help the learner. An empty array is OK.
Respond ONLY with the JSON object, no markdown fences, no extra text."""


async def handle_sentence(
    text: str,
    target_lang: str,
    explanation_lang: str,
) -> dict:
    system_prompt = _build_system_prompt(target_lang, explanation_lang)
    result = await llm_client.generate(system_prompt, text)
    parsed = parse_json_response(result.text)

    return {
        "source_text": parsed["source_text"],
        "source_reading": parsed.get("source_reading", ""),
        "translation": parsed["translation"],
        "literal_translation": parsed.get("literal_translation", ""),
        "key_points": parsed.get("key_points", []),
        "model_label": llm_client.format_model(result),
    }
