import json
import logging
import re

from llm import client as llm_client

logger = logging.getLogger(__name__)

_MAX_NEW_QUIZ_ATTEMPTS = 3
_MAX_BATCH_ATTEMPTS = 2


def _normalize_word(word: str) -> str:
    """重複判定用の正規化: 前後空白除去 + 大文字小文字無視(英語)。"""
    return word.strip().casefold()


def _lang_names(target_lang: str, explanation_lang: str) -> tuple[str, str]:
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    return target_name, explanation_name


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _parse_quiz_json(raw_response: str) -> dict:
    cleaned = _strip_code_fences(raw_response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini quiz response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e


def _parse_quiz_array(raw_response: str) -> list[dict]:
    cleaned = _strip_code_fences(raw_response)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini batch response as JSON: %r", cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of quiz objects, got {type(data).__name__}")
    return data


def _validate_quiz(parsed: dict, require_source_text: bool) -> None:
    required = ["question_text", "choices", "correct_index", "explanation"]
    if require_source_text:
        required.append("source_text")
    for key in required:
        if key not in parsed:
            raise ValueError(f"Quiz JSON missing required key: {key}")
    if not isinstance(parsed["choices"], list) or len(parsed["choices"]) != 4:
        raise ValueError(f"choices must be a list of exactly 4 items, got {parsed['choices']!r}")
    if not isinstance(parsed["correct_index"], int) or not (0 <= parsed["correct_index"] <= 3):
        raise ValueError(f"correct_index must be int in [0, 3], got {parsed['correct_index']!r}")


_LEVEL_HINT = {
    "ja": (
        "Target JLPT N3 to N2 vocabulary (intermediate to upper-intermediate). "
        "Do NOT exceed N2 difficulty. "
        "Idioms (慣用句), proverbs, and colloquial expressions are welcome — "
        "BUT prefer ones commonly used in daily Japanese conversation; "
        "avoid rare, literary, archaic, or highly technical expressions."
    ),
    "en": (
        "Target Eiken Pre-1 to IELTS 7.0 vocabulary (upper-intermediate to advanced). "
        "Idioms and colloquial expressions are welcome — "
        "BUT prefer ones commonly used in daily English conversation; "
        "avoid rare, literary, archaic, or highly technical expressions."
    ),
}


def _level_hint(target_lang: str) -> str:
    return _LEVEL_HINT.get(
        target_lang,
        "Target a common, intermediate-level vocabulary item used in daily conversation.",
    )


def _build_review_prompt(target_lang: str, explanation_lang: str) -> str:
    target_name, explanation_name = _lang_names(target_lang, explanation_lang)
    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

The learner studied a {target_name} word in the past and the word will be provided as the user message. Create a 4-option multiple-choice quiz testing whether they recall its meaning.

Return a JSON object with this exact structure:

{{
  "question_text": "a question in {explanation_name} that QUOTES the source word by name and asks for its meaning. Substitute <WORD> with the actual source word. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
  "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
  "correct_index": <int 0-3 indicating which choice is correct>,
  "explanation": "brief explanation in {explanation_name} (under 200 chars)"
}}

Rules:
- The question_text MUST quote the source word by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; the source word is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable (similar category, similar level) but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80 for Discord button label).
- Randomize the correct answer's position (do not always put it at index 0).
- Explanation should be neutral reference-book tone (no character voice, no 〜だよ / 〜だね).

Respond ONLY with the JSON object, no markdown fences, no extra text."""


def _build_new_prompt(
    target_lang: str,
    explanation_lang: str,
    history: list[str],
    exclusion_list: list[str],
) -> str:
    target_name, explanation_name = _lang_names(target_lang, explanation_lang)

    if history:
        history_section = (
            "Learner's recent study history (for topical context only — NOT a level guide):\n"
            + ", ".join(history)
        )
    else:
        history_section = "Learner has no study history yet."

    if exclusion_list:
        exclusion_section = (
            "FORBIDDEN WORDS — these were already studied or quizzed. "
            "You MUST NOT pick any of them. Picking any one is an invalid response:\n"
            + ", ".join(exclusion_list)
        )
    else:
        exclusion_section = "No exclusions."

    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

Pick ONE NEW {target_name} word the learner likely hasn't studied yet, then create a 4-option multiple-choice quiz on its meaning.

{history_section}

{exclusion_section}

Return a JSON object with this exact structure:

{{
  "source_text": "the new {target_name} word you picked",
  "question_text": "a question in {explanation_name} that QUOTES source_text by name and asks for its meaning. Substitute <WORD> with source_text. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
  "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
  "correct_index": <int 0-3 indicating which choice is correct>,
  "explanation": "brief explanation in {explanation_name} (under 200 chars)"
}}

Rules:
- The chosen source_text MUST be different from every forbidden word listed above.
- {_level_hint(target_lang)}
- The question_text MUST quote source_text by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; source_text is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80).
- Randomize the correct answer's position.
- Explanation should be neutral reference-book tone (no character voice).

Respond ONLY with the JSON object, no markdown fences, no extra text."""


def _build_new_batch_prompt(
    target_lang: str,
    explanation_lang: str,
    history: list[str],
    exclusion_list: list[str],
    count: int,
) -> str:
    target_name, explanation_name = _lang_names(target_lang, explanation_lang)

    if history:
        history_section = (
            "Learner's recent study history (for topical context only — NOT a level guide):\n"
            + ", ".join(history)
        )
    else:
        history_section = "Learner has no study history yet."

    if exclusion_list:
        exclusion_section = (
            "FORBIDDEN WORDS — these were already studied or quizzed. "
            "You MUST NOT pick any of them. Picking any one is an invalid response:\n"
            + ", ".join(exclusion_list)
        )
    else:
        exclusion_section = "No exclusions."

    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

Pick {count} DISTINCT NEW {target_name} words the learner likely hasn't studied yet, then create a 4-option multiple-choice quiz on the meaning of each.

{history_section}

{exclusion_section}

Return a JSON array of exactly {count} objects, each with this exact structure:

[
  {{
    "source_text": "the new {target_name} word you picked",
    "question_text": "a question in {explanation_name} that QUOTES source_text by name and asks for its meaning. Substitute <WORD> with source_text. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
    "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
    "correct_index": <int 0-3 indicating which choice is correct>,
    "explanation": "brief explanation in {explanation_name} (under 200 chars)"
  }}
]

Rules:
- The {count} source_text values MUST all be different from each other.
- Every source_text MUST be different from every forbidden word listed above.
- {_level_hint(target_lang)}
- Each question_text MUST quote its source_text by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; source_text is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices in each quiz are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80).
- Randomize the correct answer's position in each quiz.
- Explanation should be neutral reference-book tone (no character voice).

Respond ONLY with the JSON array, no markdown fences, no extra text."""


async def generate_review_quiz(
    source_word: str,
    target_lang: str,
    explanation_lang: str,
) -> dict:
    """過去に学習した語の 4 択復習クイズを生成。source_text は呼び出し側が指定。"""
    system_prompt = _build_review_prompt(target_lang, explanation_lang)
    result = await llm_client.generate(system_prompt, source_word)
    parsed = _parse_quiz_json(result.text)
    _validate_quiz(parsed, require_source_text=False)
    return {
        "source_text": source_word,
        "question_text": parsed["question_text"],
        "choices": parsed["choices"],
        "correct_index": parsed["correct_index"],
        "explanation": parsed["explanation"],
        "model_label": llm_client.format_model(result),
    }


async def generate_new_quiz(
    history: list[str],
    exclusion_list: list[str],
    target_lang: str,
    explanation_lang: str,
) -> dict:
    """学習者の履歴から同レベルの未学習語を 1 つ選び、4 択クイズを生成。

    除外語が返ってきた場合はその語を除外に足して再生成し、重複を出さないことをコード側で保証する。
    最大 _MAX_NEW_QUIZ_ATTEMPTS 回試して全て重複だった場合は ValueError。
    """
    current_exclusion = list(exclusion_list)
    excluded_norm = {_normalize_word(w) for w in current_exclusion}

    for attempt in range(_MAX_NEW_QUIZ_ATTEMPTS):
        system_prompt = _build_new_prompt(
            target_lang, explanation_lang, history, current_exclusion,
        )
        result = await llm_client.generate(
            system_prompt, "Pick a new word and create a quiz.",
        )
        parsed = _parse_quiz_json(result.text)
        _validate_quiz(parsed, require_source_text=True)
        source_text = parsed["source_text"]

        if _normalize_word(source_text) not in excluded_norm:
            return {
                "source_text": source_text,
                "question_text": parsed["question_text"],
                "choices": parsed["choices"],
                "correct_index": parsed["correct_index"],
                "explanation": parsed["explanation"],
                "model_label": llm_client.format_model(result),
            }

        logger.warning(
            "Gemini returned excluded word %r (attempt %d/%d); retrying",
            source_text, attempt + 1, _MAX_NEW_QUIZ_ATTEMPTS,
        )
        current_exclusion.append(source_text)
        excluded_norm.add(_normalize_word(source_text))

    raise ValueError(
        f"Could not generate a non-duplicate new word after {_MAX_NEW_QUIZ_ATTEMPTS} attempts"
    )


async def generate_new_quiz_batch(
    count: int,
    history: list[str],
    exclusion_list: list[str],
    target_lang: str,
    explanation_lang: str,
) -> list[dict]:
    """互いに異なる未学習語 count 個の 4 択クイズを、なるべく少ない API コールで生成。

    1 コールで count 個を要求し、バッチ内重複・除外語との重複をコード側で排除する。
    不足した分だけ最大 _MAX_BATCH_ATTEMPTS 回まで追撃する。
    全コールでも揃わない場合は集まった分だけ返す(重複は絶対に含めない)。
    """
    collected: list[dict] = []
    seen_norm = {_normalize_word(w) for w in exclusion_list}
    current_exclusion = list(exclusion_list)

    for _ in range(_MAX_BATCH_ATTEMPTS):
        missing = count - len(collected)
        if missing <= 0:
            break

        system_prompt = _build_new_batch_prompt(
            target_lang, explanation_lang, history, current_exclusion, missing,
        )
        result = await llm_client.generate(
            system_prompt, f"Pick {missing} new words and create quizzes.",
        )
        model_label = llm_client.format_model(result)

        for parsed in _parse_quiz_array(result.text):
            try:
                _validate_quiz(parsed, require_source_text=True)
            except ValueError:
                logger.warning("Skipping malformed quiz object in batch: %r", parsed)
                continue

            source_text = parsed["source_text"]
            norm = _normalize_word(source_text)
            if norm in seen_norm:
                continue

            seen_norm.add(norm)
            current_exclusion.append(source_text)
            collected.append({
                "source_text": source_text,
                "question_text": parsed["question_text"],
                "choices": parsed["choices"],
                "correct_index": parsed["correct_index"],
                "explanation": parsed["explanation"],
                "model_label": model_label,
            })
            if len(collected) >= count:
                break

    if len(collected) < count:
        logger.warning(
            "Batch produced only %d/%d new quizzes after %d attempts",
            len(collected), count, _MAX_BATCH_ATTEMPTS,
        )
    return collected[:count]
