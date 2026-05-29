import pytest

from llm import client as llm_client
from llm.errors import LLMError, LLMRateLimitError


def _backend(result=None, exc=None, recorder=None, name="b"):
    async def fn(system_prompt, user_prompt, model):
        if recorder is not None:
            recorder.append(name)
        if exc is not None:
            raise exc
        return result

    return fn


class TestRunChain:
    async def test_returns_first_backend_result(self):
        called = []
        chain = [
            (_backend(result="A", recorder=called, name="a"), "m1", "a"),
            (_backend(result="B", recorder=called, name="b"), "m2", "b"),
        ]

        out = await llm_client._run_chain(chain, "sys", "user")

        assert out == "A"
        assert called == ["a"]

    async def test_falls_back_on_rate_limit(self):
        called = []
        chain = [
            (_backend(exc=LLMRateLimitError("429"), recorder=called, name="a"), "m1", "a"),
            (_backend(result="B", recorder=called, name="b"), "m2", "b"),
        ]

        out = await llm_client._run_chain(chain, "sys", "user")

        assert out == "B"
        assert called == ["a", "b"]

    async def test_raises_llm_error_when_all_exhausted(self):
        chain = [
            (_backend(exc=LLMRateLimitError("429")), "m1", "a"),
            (_backend(exc=LLMRateLimitError("429")), "m2", "b"),
        ]

        with pytest.raises(LLMError):
            await llm_client._run_chain(chain, "sys", "user")

    async def test_non_rate_error_propagates_without_fallback(self):
        called = []
        chain = [
            (_backend(exc=ValueError("bad prompt"), recorder=called, name="a"), "m1", "a"),
            (_backend(result="B", recorder=called, name="b"), "m2", "b"),
        ]

        with pytest.raises(ValueError):
            await llm_client._run_chain(chain, "sys", "user")

        assert called == ["a"]


class TestBuildChain:
    def test_gemini_only_when_openrouter_unset(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        chain = llm_client._build_chain()

        assert [label for _, _, label in chain] == ["gemini", "gemini"]

    def test_appends_openrouter_when_both_env_set(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")

        chain = llm_client._build_chain()

        assert [label for _, _, label in chain] == ["gemini", "gemini", "openrouter"]
        assert chain[-1][1] == "vendor/model"

    def test_skips_openrouter_when_only_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        chain = llm_client._build_chain()

        assert [label for _, _, label in chain] == ["gemini", "gemini"]
