import pytest

from handlers import router
from llm import gemini_client


class TestClassifyInput:
    async def test_returns_word_when_llm_says_word(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "word"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_returns_sentence_when_llm_says_sentence(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "sentence"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("Could you pick me up?")
        assert result == "sentence"

    async def test_returns_grammar_when_llm_says_grammar(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "grammar"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("What does 〜てしまう mean?")
        assert result == "grammar"

    async def test_strips_whitespace_and_normalizes_case(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "  WORD  \n"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_strips_trailing_punctuation(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "sentence."

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("Could you pick me up?")
        assert result == "sentence"

    async def test_strips_surrounding_quotes(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return '"grammar"'

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("What does X mean?")
        assert result == "grammar"

    async def test_defaults_to_word_on_unrecognized_response(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "This is a very long unexpected response"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("apple")
        assert result == "word"

    async def test_defaults_to_word_on_empty_response(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return ""

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await router.classify_input("apple")
        assert result == "word"
