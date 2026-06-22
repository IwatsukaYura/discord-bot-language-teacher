"""LLM 応答テキストの共通パース処理。

各ハンドラ (word / sentence / grammar / quiz) で重複していた
「コードフェンス除去 → JSON パース → 失敗時ログ + ValueError」を一元化する。
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """応答全体を囲う ```json フェンスを除去する。フェンスが無ければそのまま返す。"""
    text = text.strip()
    match = _CODE_FENCE_PATTERN.match(text)
    return match.group(1).strip() if match else text


def parse_json_response(raw_response: str, context: str = "response") -> Any:
    """フェンス除去 + JSON パース。失敗時はログを残して ValueError を送出する。

    context はログメッセージの識別用 (例: "quiz response", "batch response")。
    """
    cleaned = strip_code_fences(raw_response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini %s as JSON: %r", context, cleaned)
        raise ValueError(f"Invalid JSON from Gemini: {e}") from e
