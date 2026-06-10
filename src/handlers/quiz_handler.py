"""クイズ生成のオーケストレーション。

プロンプト構築は quiz.prompts、応答のパース/検証は quiz.parsing に分離し、
このモジュールは LLM 呼び出しとリトライ・重複排除の制御だけを担当する。
"""

import logging

from llm import client as llm_client
from quiz import prompts
from quiz.models import QuizContent
from quiz.parsing import (
    build_quiz_content,
    normalize_word,
    parse_quiz_array,
    parse_quiz_json,
    validate_quiz,
)

logger = logging.getLogger(__name__)

_MAX_NEW_QUIZ_ATTEMPTS = 3
_MAX_BATCH_ATTEMPTS = 2


async def generate_review_quiz(
    source_word: str,
    target_lang: str,
    explanation_lang: str,
) -> QuizContent:
    """過去に学習した語の 4 択復習クイズを生成。source_text は呼び出し側が指定。"""
    system_prompt = prompts.build_review_prompt(target_lang, explanation_lang)
    result = await llm_client.generate(system_prompt, source_word)
    parsed = parse_quiz_json(result.text)
    validate_quiz(parsed, require_source_text=False)
    return build_quiz_content(parsed, source_word, llm_client.format_model(result))


async def generate_new_quiz(
    history: list[str],
    exclusion_list: list[str],
    target_lang: str,
    explanation_lang: str,
) -> QuizContent:
    """学習者の履歴から同レベルの未学習語を 1 つ選び、4 択クイズを生成。

    除外語が返ってきた場合はその語を除外に足して再生成し、重複を出さないことをコード側で保証する。
    最大 _MAX_NEW_QUIZ_ATTEMPTS 回試して全て重複だった場合は ValueError。
    """
    current_exclusion = list(exclusion_list)
    excluded_norm = {normalize_word(w) for w in current_exclusion}

    for attempt in range(_MAX_NEW_QUIZ_ATTEMPTS):
        system_prompt = prompts.build_new_prompt(
            target_lang, explanation_lang, history, current_exclusion,
        )
        result = await llm_client.generate(
            system_prompt, "Pick a new word and create a quiz.",
        )
        parsed = parse_quiz_json(result.text)
        validate_quiz(parsed, require_source_text=True)
        source_text = parsed["source_text"]

        if normalize_word(source_text) not in excluded_norm:
            return build_quiz_content(parsed, source_text, llm_client.format_model(result))

        logger.warning(
            "Gemini returned excluded word %r (attempt %d/%d); retrying",
            source_text, attempt + 1, _MAX_NEW_QUIZ_ATTEMPTS,
        )
        current_exclusion.append(source_text)
        excluded_norm.add(normalize_word(source_text))

    raise ValueError(
        f"Could not generate a non-duplicate new word after {_MAX_NEW_QUIZ_ATTEMPTS} attempts"
    )


async def generate_new_quiz_batch(
    count: int,
    history: list[str],
    exclusion_list: list[str],
    target_lang: str,
    explanation_lang: str,
) -> list[QuizContent]:
    """互いに異なる未学習語 count 個の 4 択クイズを、なるべく少ない API コールで生成。

    1 コールで count 個を要求し、バッチ内重複・除外語との重複をコード側で排除する。
    不足した分だけ最大 _MAX_BATCH_ATTEMPTS 回まで追撃する。
    全コールでも揃わない場合は集まった分だけ返す(重複は絶対に含めない)。
    """
    collected: list[QuizContent] = []
    seen_norm = {normalize_word(w) for w in exclusion_list}
    current_exclusion = list(exclusion_list)

    for _ in range(_MAX_BATCH_ATTEMPTS):
        missing = count - len(collected)
        if missing <= 0:
            break

        system_prompt = prompts.build_new_batch_prompt(
            target_lang, explanation_lang, history, current_exclusion, missing,
        )
        result = await llm_client.generate(
            system_prompt, f"Pick {missing} new words and create quizzes.",
        )
        model_label = llm_client.format_model(result)

        for parsed in parse_quiz_array(result.text):
            try:
                validate_quiz(parsed, require_source_text=True)
            except ValueError:
                logger.warning("Skipping malformed quiz object in batch: %r", parsed)
                continue

            source_text = parsed["source_text"]
            norm = normalize_word(source_text)
            if norm in seen_norm:
                continue

            seen_norm.add(norm)
            current_exclusion.append(source_text)
            collected.append(build_quiz_content(parsed, source_text, model_label))
            if len(collected) >= count:
                break

    if len(collected) < count:
        logger.warning(
            "Batch produced only %d/%d new quizzes after %d attempts",
            len(collected), count, _MAX_BATCH_ATTEMPTS,
        )
    return collected[:count]
