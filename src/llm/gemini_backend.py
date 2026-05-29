import os

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from llm.errors import LLMRateLimitError

# 404: モデル不在(名称変更等), 429: レート/クォータ超過, 5xx: サーバ過負荷。いずれも別モデルへフォールバック。
_FALLBACK_CODES = {404, 429, 500, 502, 503}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


async def generate(system_prompt: str, user_prompt: str, model: str) -> str:
    client = _get_client()
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
    except genai_errors.APIError as e:
        if e.code in _FALLBACK_CODES:
            raise LLMRateLimitError(f"Gemini {model} returned {e.code} ({e.status})") from e
        raise
    return response.text
