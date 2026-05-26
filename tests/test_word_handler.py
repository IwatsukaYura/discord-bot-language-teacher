import json

import pytest

from handlers import word_handler
from llm import gemini_client


MOCK_VALID_RESPONSE = json.dumps({
    "headword": "apple",
    "translation": "リンゴ",
    "part_of_speech": "noun",
    "meaning": "A round fruit",
    "usage": "common everyday word",
    "examples": [
        {"source": "I ate an apple.", "translation": "りんごを食べた。"},
        {"source": "She likes apples.", "translation": "彼女はりんごが好きです。"},
    ],
})


class TestBuildSystemPrompt:
    def test_for_english_learner_mentions_english_teacher_and_japanese_speakers(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "English language teacher" in prompt
        assert "Japanese speakers" in prompt

    def test_for_japanese_learner_mentions_japanese_teacher_and_english_speakers(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "Japanese language teacher" in prompt
        assert "English speakers" in prompt

    def test_mentions_reverse_lookup_behavior(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "equivalent" in prompt.lower()


class TestStripCodeFences:
    def test_removes_json_labeled_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert word_handler._strip_code_fences(text) == '{"a": 1}'

    def test_removes_plain_fence(self):
        text = '```\n{"a": 1}\n```'
        assert word_handler._strip_code_fences(text) == '{"a": 1}'

    def test_passes_through_when_no_fence(self):
        text = '{"a": 1}'
        assert word_handler._strip_code_fences(text) == '{"a": 1}'

    def test_strips_leading_and_trailing_whitespace(self):
        text = '   {"a": 1}   '
        assert word_handler._strip_code_fences(text) == '{"a": 1}'


class TestBuildDictionaryUrl:
    def test_english_word_is_inserted_as_is(self):
        url = word_handler._build_dictionary_url("apple", "https://example.com/{word}")
        assert url == "https://example.com/apple"

    def test_japanese_word_is_url_encoded(self):
        url = word_handler._build_dictionary_url("林檎", "https://example.com/{word}")
        assert url == "https://example.com/%E6%9E%97%E6%AA%8E"


class TestHandleWord:
    async def test_returns_structured_dict_on_valid_response(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_VALID_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["word"] == "apple"
        assert result["translation"] == "リンゴ"
        assert result["part_of_speech"] == "noun"
        assert result["meaning"] == "A round fruit"
        assert result["usage"] == "common everyday word"
        assert len(result["examples"]) == 2
        assert result["examples"][0]["source"] == "I ate an apple."
        assert result["dictionary_url"] == "https://example.com/apple"

    async def test_handles_response_wrapped_in_code_fences(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return f"```json\n{MOCK_VALID_RESPONSE}\n```"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["translation"] == "リンゴ"

    async def test_raises_value_error_on_invalid_json(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "this is not json"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        with pytest.raises(ValueError, match="Invalid JSON from Gemini"):
            await word_handler.handle_word(
                word="apple",
                target_lang="en",
                explanation_lang="ja",
                dictionary_url_template="https://example.com/{word}",
            )

    async def test_url_encodes_japanese_word_for_dictionary_link(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "headword": "林檎",
                "translation": "apple",
                "reading": "りんご",
                "part_of_speech": "noun",
                "meaning": "...",
                "usage": "...",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="林檎",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["dictionary_url"] == "https://jisho.org/search/%E6%9E%97%E6%AA%8E"

    async def test_includes_reading_when_target_is_japanese(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "headword": "視察",
                "translation": "inspection",
                "reading": "しさつ",
                "part_of_speech": "noun / suru-verb",
                "meaning": "visiting a location to observe",
                "usage": "official contexts",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="視察",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["reading"] == "しさつ"

    async def test_reading_defaults_to_empty_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_VALID_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["reading"] == ""

    async def test_reverse_lookup_uses_headword_as_word(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "headword": "りんご",
                "translation": "apple",
                "reading": "",
                "part_of_speech": "noun",
                "meaning": "round red/green fruit",
                "usage": "everyday word",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["word"] == "りんご"
        assert "%E3%82%8A%E3%82%93%E3%81%94" in result["dictionary_url"]

    async def test_reverse_lookup_includes_reading_for_kanji_headword(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "headword": "机",
                "translation": "desk",
                "reading": "つくえ",
                "part_of_speech": "noun",
                "meaning": "furniture you sit at",
                "usage": "everyday word",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="desk",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["word"] == "机"
        assert result["reading"] == "つくえ"


class TestBuildSystemPromptReading:
    def test_japanese_target_includes_reading_field(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert '"reading"' in prompt

    def test_english_target_omits_reading_field(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert '"reading"' not in prompt
