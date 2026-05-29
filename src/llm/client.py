import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from llm.errors import LLMError, LLMRateLimitError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    """生成結果と、実際に応答したモデル/プロバイダ。"""

    text: str
    model: str
    provider: str


def format_model(result: LLMResult) -> str:
    """フッター表示用のモデル名。OpenRouter はプロバイダ名も併記する。"""
    if result.provider == "gemini":
        return result.model
    return f"{result.provider} · {result.model}"

# 各バックエンドは async 呼び出し: (system_prompt, user_prompt, model) -> str
Backend = Callable[[str, str, str], Awaitable[str]]
# チェーン要素: (backend, model, label)
ChainStep = tuple[Backend, str, str]

_GEMINI_PRIMARY = "gemini-3.1-flash-lite"
_GEMINI_SECONDARY = "gemini-3.1-flash"


def _build_chain() -> list[ChainStep]:
    """優先順のフォールバックチェーンを構築する。

    OpenRouter は API キーとモデルの両方が設定されている場合だけ末尾に加える。
    """
    from llm import gemini_backend, openrouter_backend

    chain: list[ChainStep] = [
        (gemini_backend.generate, _GEMINI_PRIMARY, "gemini"),
        (gemini_backend.generate, _GEMINI_SECONDARY, "gemini"),
    ]

    openrouter_model = os.getenv("OPENROUTER_MODEL")
    if os.getenv("OPENROUTER_API_KEY") and openrouter_model:
        chain.append((openrouter_backend.generate, openrouter_model, "openrouter"))

    return chain


async def _run_chain(
    chain: list[ChainStep], system_prompt: str, user_prompt: str,
) -> LLMResult:
    """チェーンを順に試す。レート超過/過負荷なら次へ、それ以外の例外は即座に伝播。"""
    last_error: LLMRateLimitError | None = None
    for backend, model, label in chain:
        try:
            text = await backend(system_prompt, user_prompt, model)
        except LLMRateLimitError as e:
            logger.warning(
                "LLM backend %s (model=%s) unavailable; falling back: %s", label, model, e,
            )
            last_error = e
            continue
        logger.info("LLM responded via %s (model=%s)", label, model)
        return LLMResult(text=text, model=model, provider=label)
    raise LLMError("All LLM backends are exhausted") from last_error


async def generate(system_prompt: str, user_prompt: str) -> LLMResult:
    """フォールバックチェーン経由で 1 回の生成を行う公開エントリ。"""
    return await _run_chain(_build_chain(), system_prompt, user_prompt)
