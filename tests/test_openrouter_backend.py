from types import SimpleNamespace

import httpx
import openai
import pytest

from llm import openrouter_backend
from llm.errors import LLMRateLimitError


def _status_error(code: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "http://x")
    response = httpx.Response(code, request=request)
    return openai.APIStatusError("err", response=response, body=None)


class FakeCompletions:
    def __init__(self, exc=None, content="ok"):
        self.exc = exc
        self.content = content
        self.last = None

    async def create(self, model, messages):
        self.last = {"model": model, "messages": messages}
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


class FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


@pytest.fixture(autouse=True)
def _reset_client():
    openrouter_backend._client = None
    yield
    openrouter_backend._client = None


class TestOpenRouterBackend:
    async def test_returns_content_on_success(self, monkeypatch):
        completions = FakeCompletions(content="hello")
        monkeypatch.setattr(openrouter_backend, "_get_client", lambda: FakeClient(completions))

        out = await openrouter_backend.generate("sys", "user", "some/model")

        assert out == "hello"
        assert completions.last["model"] == "some/model"
        roles = [m["role"] for m in completions.last["messages"]]
        assert roles == ["system", "user"]

    @pytest.mark.parametrize("code", [429, 500, 502, 503])
    async def test_maps_rate_and_overload_codes(self, monkeypatch, code):
        completions = FakeCompletions(exc=_status_error(code))
        monkeypatch.setattr(openrouter_backend, "_get_client", lambda: FakeClient(completions))

        with pytest.raises(LLMRateLimitError):
            await openrouter_backend.generate("sys", "user", "m")

    async def test_reraises_other_status_errors(self, monkeypatch):
        completions = FakeCompletions(exc=_status_error(400))
        monkeypatch.setattr(openrouter_backend, "_get_client", lambda: FakeClient(completions))

        with pytest.raises(openai.APIStatusError):
            await openrouter_backend.generate("sys", "user", "m")
