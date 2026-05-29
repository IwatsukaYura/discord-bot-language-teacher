from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from llm import gemini_backend
from llm.errors import LLMRateLimitError


class FakeModels:
    def __init__(self, exc=None, text="ok"):
        self.exc = exc
        self.text = text
        self.last_model = None

    async def generate_content(self, model, contents, config):
        self.last_model = model
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(text=self.text)


class FakeClient:
    def __init__(self, models):
        self.aio = SimpleNamespace(models=models)


@pytest.fixture(autouse=True)
def _reset_client():
    gemini_backend._client = None
    yield
    gemini_backend._client = None


class TestGeminiBackend:
    async def test_returns_text_on_success(self, monkeypatch):
        models = FakeModels(text="hello")
        monkeypatch.setattr(gemini_backend, "_get_client", lambda: FakeClient(models))

        out = await gemini_backend.generate("sys", "user", "gemini-3.1-flash-lite")

        assert out == "hello"
        assert models.last_model == "gemini-3.1-flash-lite"

    @pytest.mark.parametrize("code", [429, 500, 502, 503])
    async def test_maps_rate_and_overload_codes(self, monkeypatch, code):
        models = FakeModels(exc=genai_errors.APIError(code, {}))
        monkeypatch.setattr(gemini_backend, "_get_client", lambda: FakeClient(models))

        with pytest.raises(LLMRateLimitError):
            await gemini_backend.generate("sys", "user", "m")

    async def test_reraises_other_api_errors(self, monkeypatch):
        models = FakeModels(exc=genai_errors.APIError(400, {}))
        monkeypatch.setattr(gemini_backend, "_get_client", lambda: FakeClient(models))

        with pytest.raises(genai_errors.APIError):
            await gemini_backend.generate("sys", "user", "m")
