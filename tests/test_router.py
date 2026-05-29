import pytest

from handlers import router
from llm import client as llm_client


def _fake_generate(text):
    async def gen(system_prompt, user_prompt):
        return llm_client.LLMResult(text=text, model="test-model", provider="gemini")

    return gen


class TestClassifyInput:
    async def test_returns_word_when_llm_says_word(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("word"))
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_returns_sentence_when_llm_says_sentence(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("sentence"))
        result = await router.classify_input("Could you pick me up?")
        assert result == "sentence"

    async def test_returns_grammar_when_llm_says_grammar(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("grammar"))
        result = await router.classify_input("What does 〜てしまう mean?")
        assert result == "grammar"

    async def test_strips_whitespace_and_normalizes_case(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("  WORD  \n"))
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_strips_trailing_punctuation(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("sentence."))
        result = await router.classify_input("Could you pick me up?")
        assert result == "sentence"

    async def test_strips_surrounding_quotes(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate('"grammar"'))
        result = await router.classify_input("What does X mean?")
        assert result == "grammar"

    async def test_defaults_to_word_on_unrecognized_response(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate("This is a very long unexpected response"))
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_defaults_to_word_on_empty_response(self, monkeypatch):
        monkeypatch.setattr(llm_client, "generate", _fake_generate(""))
        result = await router.classify_input("apple")
        assert result == "word"
