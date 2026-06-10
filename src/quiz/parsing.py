"""クイズ生成 LLM 応答のパースとバリデーション。

handlers.quiz_handler から分離。JSON 構造の検証と quiz_content dict の
組み立てだけを担当し、LLM 呼び出しやリトライ制御は持たない。
"""

import logging

from llm.parsing import parse_json_response
from quiz.models import QuizContent

logger = logging.getLogger(__name__)


def normalize_word(word: str) -> str:
    """重複判定用の正規化: 前後空白除去 + 大文字小文字無視(英語)。"""
    return word.strip().casefold()


def parse_quiz_json(raw_response: str) -> dict:
    return parse_json_response(raw_response, context="quiz response")


def parse_quiz_array(raw_response: str) -> list[dict]:
    data = parse_json_response(raw_response, context="batch response")
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of quiz objects, got {type(data).__name__}")
    return data


def _extract_optional_str(parsed: dict, key: str) -> str:
    """JSON にキーがあれば trim した文字列を、無ければ空文字を返す。

    LLM が文字列以外(None/数値など)を返した場合も空文字にフォールバック。
    """
    value = parsed.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""


def validate_quiz(parsed: dict, require_source_text: bool) -> None:
    """必須キーと choices/correct_index の形式を検証。違反は ValueError。"""
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


def build_quiz_content(parsed: dict, source_text: str, model_label: str) -> QuizContent:
    """検証済みの parsed JSON から QuizContent を組み立てる。"""
    return QuizContent(
        source_text=source_text,
        question_text=parsed["question_text"],
        choices=tuple(parsed["choices"]),
        correct_index=parsed["correct_index"],
        explanation=parsed["explanation"],
        reading=_extract_optional_str(parsed, "reading"),
        example_sentence=_extract_optional_str(parsed, "example_sentence"),
        model_label=model_label,
    )
