class LLMError(Exception):
    """LLM プロバイダ共通の基底例外。"""


class LLMRateLimitError(LLMError):
    """レート/クォータ超過、または 5xx 過負荷。フォールバック対象として扱う。"""
