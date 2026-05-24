import os

from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.1-flash-lite"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


async def generate(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )
    return response.text
