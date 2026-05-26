import json

import pytest

from handlers import word_handler
from llm import gemini_client


MOCK_SINGLE_SENSE_RESPONSE = json.dumps({
    "headword": "apple",
    "reading": "",
    "part_of_speech": "noun",
    "senses": [
        {
            "translations": [
                {"text": "リンゴ", "reading": ""},
            ],
            "meaning": "A round red or green fruit.",
            "usage": "Everyday word.",
            "examples": [
                {"source": "I ate an apple.", "translation": "りんごを食べた。"},
                {"source": "She likes apples.", "translation": "彼女はりんごが好きです。"},
            ],
        }
    ],
})


MOCK_MULTI_SENSE_RESPONSE = json.dumps({
    "headword": "retrieval",
    "reading": "",
    "part_of_speech": "noun",
    "senses": [
        {
            "translations": [
                {"text": "検索", "reading": ""},
                {"text": "取り出し", "reading": ""},
            ],
            "meaning": "情報を取り出すこと",
            "usage": "技術文脈で頻出",
            "examples": [
                {"source": "I retrieve records from the DB.", "translation": "DBからレコードを取り出す。"},
                {"source": "Data retrieval is fast here.", "translation": "ここはデータの取り出しが速い。"},
            ],
        },
        {
            "translations": [
                {"text": "回収", "reading": ""},
            ],
            "meaning": "失った物を取り戻すこと",
            "usage": "物理的なものに使う",
            "examples": [
                {"source": "The dog retrieves the ball.", "translation": "犬がボールを回収する。"},
                {"source": "He retrieved his lost wallet.", "translation": "彼は失くした財布を回収した。"},
            ],
        },
    ],
})


MOCK_JA_TARGET_RESPONSE = json.dumps({
    "headword": "検索",
    "reading": "けんさく",
    "part_of_speech": "noun / suru-verb",
    "senses": [
        {
            "translations": [
                {"text": "検索", "reading": "けんさく"},
                {"text": "取り出し", "reading": "とりだし"},
            ],
            "meaning": "Retrieving information from a database or server.",
            "usage": "Common in technical contexts.",
            "examples": [
                {"source": "データベースからレコードを取り出す。", "translation": "I retrieve records from the database."},
                {"source": "サーバーからログを取り出した。", "translation": "I retrieved logs from the server."},
            ],
        }
    ],
})


class TestBuildSystemPrompt:
    def test_for_english_learner_mentions_english_dictionary_and_japanese_speakers(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "English dictionary" in prompt
        assert "Japanese speakers" in prompt

    def test_for_japanese_learner_mentions_japanese_dictionary_and_english_speakers(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "Japanese dictionary" in prompt
        assert "English speakers" in prompt

    def test_mentions_reverse_lookup_behavior(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "equivalent" in prompt.lower()

    def test_mentions_senses_split_rule(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "senses" in prompt.lower()
        assert "distinct meaning" in prompt.lower()

    def test_mentions_translation_must_contain_user_input(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        # 例文 translation に user 入力(またはその活用形)を含めることを必須とする指示が存在
        assert "inflection" in prompt.lower()

    def test_japanese_target_requires_reading_for_kanji_in_translations(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "hiragana" in prompt.lower()

    def test_english_target_forces_empty_translation_readings(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "empty strings" in prompt.lower() or "MUST be empty" in prompt


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
    async def test_returns_structured_dict_for_single_sense(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_SINGLE_SENSE_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["word"] == "apple"
        assert result["reading"] == ""
        assert result["part_of_speech"] == "noun"
        assert len(result["senses"]) == 1
        sense = result["senses"][0]
        assert sense["translations"] == [{"text": "リンゴ", "reading": ""}]
        assert sense["meaning"] == "A round red or green fruit."
        assert len(sense["examples"]) == 2
        assert result["dictionary_url"] == "https://example.com/apple"

    async def test_returns_multiple_senses_for_polysemous_word(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_MULTI_SENSE_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="retrieval",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["word"] == "retrieval"
        assert len(result["senses"]) == 2
        assert [t["text"] for t in result["senses"][0]["translations"]] == ["検索", "取り出し"]
        assert [t["text"] for t in result["senses"][1]["translations"]] == ["回収"]

    async def test_reverse_lookup_uses_headword_as_word_with_reading(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_JA_TARGET_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="retrieval",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["word"] == "検索"
        assert result["reading"] == "けんさく"
        # 各 translation エントリに reading が付いていること
        translations = result["senses"][0]["translations"]
        assert {"text": "検索", "reading": "けんさく"} in translations
        assert {"text": "取り出し", "reading": "とりだし"} in translations

    async def test_handles_response_wrapped_in_code_fences(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return f"```json\n{MOCK_SINGLE_SENSE_RESPONSE}\n```"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["senses"][0]["translations"][0]["text"] == "リンゴ"

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

    async def test_reading_defaults_to_empty_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "headword": "apple",
                "part_of_speech": "noun",
                "senses": [{
                    "translations": [{"text": "リンゴ", "reading": ""}],
                    "meaning": "...",
                    "usage": "...",
                    "examples": [],
                }],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["reading"] == ""

    async def test_url_encodes_japanese_headword(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_JA_TARGET_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="retrieval",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        # "検索" の URL エンコード
        assert "%E6%A4%9C%E7%B4%A2" in result["dictionary_url"]
