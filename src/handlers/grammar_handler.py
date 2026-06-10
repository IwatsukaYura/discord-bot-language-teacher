import logging

from lib.lang import lang_names
from llm import client as llm_client
from llm.parsing import parse_json_response

logger = logging.getLogger(__name__)


def _build_system_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name, explanation_name = lang_names(target_lang, explanation_lang)
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


async def handle_grammar(text: str, target_lang: str, explanation_lang: str) -> dict:
    system_prompt = _build_system_prompt(target_lang, explanation_lang)
    result = await llm_client.generate(system_prompt, text)
    parsed = parse_json_response(result.text)

    return {
        "topic": parsed["topic"],
        "target_lang": target_lang,
        "explanation_lang": explanation_lang,
        "explanation": parsed["explanation"],
        "examples": parsed.get("examples", []),
        "related": parsed.get("related", ""),
        "model_label": llm_client.format_model(result),
    }
