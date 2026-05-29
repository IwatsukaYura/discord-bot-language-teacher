import os

from openai import APIStatusError, AsyncOpenAI

from llm.errors import LLMRateLimitError

_BASE_URL = "https://openrouter.ai/api/v1"
# 429: レート/クォータ超過, 5xx: サーバ過負荷。いずれもフォールバック対象。
_FALLBACK_CODES = {429, 500, 502, 503}

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in environment")
        _client = AsyncOpenAI(api_key=api_key, base_url=_BASE_URL)
    return _client


async def generate(system_prompt: str, user_prompt: str, model: str) -> str:
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except APIStatusError as e:
        if e.status_code in _FALLBACK_CODES:
            raise LLMRateLimitError(
                f"OpenRouter {model} returned {e.status_code}"
            ) from e
        raise
    return response.choices[0].message.content
