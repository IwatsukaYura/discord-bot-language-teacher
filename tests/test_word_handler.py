import json

import pytest

from handlers import word_handler
from llm import gemini_client


MOCK_SINGLE_SENSE_EN_TARGET = json.dumps({
    "input": "apple",
    "mode": "A",
    "senses": [
        {
            "headword": "apple",
            "headword_reading": "",
            "part_of_speech": "noun",
            "translations": ["リンゴ"],
            "meaning": "赤や緑の皮を持つ果物",
            "usage": "日常語",
            "examples": [
                {"source": "I ate an apple.", "translation": "りんごを食べた。"},
                {"source": "She likes apples.", "translation": "彼女はりんごが好きです。"},
            ],
        }
    ],
})


MOCK_MULTI_SENSE_EN_DIRECT_LOOKUP = json.dumps({
    "input": "bank",
    "mode": "A",
    "senses": [
        {
            "headword": "bank",
            "headword_reading": "",
            "part_of_speech": "noun",
            "translations": ["銀行"],
            "meaning": "お金を預けたり借りたりする金融機関",
            "usage": "最も一般的な意味",
            "examples": [
                {"source": "I went to the bank to withdraw cash.", "translation": "現金を引き出すために銀行へ行った。"},
                {"source": "The bank closes at 3 PM.", "translation": "銀行は午後3時に閉まる。"},
            ],
        },
        {
            "headword": "bank",
            "headword_reading": "",
            "part_of_speech": "noun",
            "translations": ["土手", "川岸"],
            "meaning": "川や湖のふち、土手",
            "usage": "地形を指すとき",
            "examples": [
                {"source": "We had a picnic on the bank of the river.", "translation": "川の土手でピクニックをした。"},
                {"source": "Trees grew along the bank.", "translation": "土手沿いに木々が生えていた。"},
            ],
        },
    ],
})


MOCK_MULTI_SENSE_JA_REVERSE_LOOKUP = json.dumps({
    "input": "retrieval",
    "mode": "B",
    "senses": [
        {
            "headword": "検索",
            "headword_reading": "けんさく",
            "part_of_speech": "noun / suru-verb",
            "translations": ["search", "retrieval", "lookup"],
            "meaning": "Retrieving information from a database or server.",
            "usage": "Common in technical contexts.",
            "examples": [
                {"source": "データベースからレコードを検索する。", "translation": "I retrieve records from the database."},
                {"source": "素早く情報を検索する。", "translation": "Search information quickly with retrieval."},
            ],
        },
        {
            "headword": "回収",
            "headword_reading": "かいしゅう",
            "part_of_speech": "noun / suru-verb",
            "translations": ["recovery", "collection"],
            "meaning": "Bringing back a lost item.",
            "usage": "Used for physical objects.",
            "examples": [
                {"source": "犬がボールを回収する。", "translation": "The dog retrieves the ball."},
                {"source": "失くした財布を回収した。", "translation": "I retrieved the lost wallet."},
            ],
        },
    ],
})


MOCK_JA_DIRECT_LOOKUP = json.dumps({
    "input": "視察",
    "mode": "A",
    "senses": [
        {
            "headword": "視察",
            "headword_reading": "しさつ",
            "part_of_speech": "noun / suru-verb",
            "translations": ["inspection", "observation visit"],
            "meaning": "Visiting a location to observe and inspect.",
            "usage": "Used in official or formal contexts.",
            "examples": [
                {"source": "現場を視察する。", "translation": "I inspect the site."},
                {"source": "工場を視察した。", "translation": "I visited the factory for inspection."},
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

    def test_japanese_target_requires_reading_for_kanji(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "hiragana" in prompt.lower()

    def test_english_target_forces_empty_readings(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "MUST be empty strings" in prompt

    def test_describes_mode_a_direct_lookup(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        assert "MODE A" in prompt
        assert "DIRECT LOOKUP" in prompt
        # 順引き時は全 sense 同 headword + 意味で分割の指示が含まれる
        assert "SAME `headword`" in prompt

    def test_describes_mode_b_reverse_lookup(self):
        prompt = word_handler._build_system_prompt(target_lang="ja", explanation_lang="en")
        assert "MODE B" in prompt
        assert "REVERSE LOOKUP" in prompt
        # 逆引き時のみ translation に user input を含める指示が含まれる
        assert "MUST contain the user's submitted" in prompt

    def test_mode_a_warns_against_injecting_target_word_into_translation(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        # MODE A では translation に target_lang の語を入れないこと
        assert "Do NOT inject" in prompt

    def test_requires_translations_array_per_sense(self):
        prompt = word_handler._build_system_prompt(target_lang="en", explanation_lang="ja")
        # 各 sense に translations 配列を要求する指示
        assert '"translations"' in prompt


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
            return MOCK_SINGLE_SENSE_EN_TARGET

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["input"] == "apple"
        assert len(result["senses"]) == 1
        sense = result["senses"][0]
        assert sense["headword"] == "apple"
        assert sense["headword_reading"] == ""
        assert sense["part_of_speech"] == "noun"
        assert len(sense["examples"]) == 2
        assert result["dictionary_url"] == "https://example.com/apple"

    async def test_sense_includes_translations_list(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_SINGLE_SENSE_EN_TARGET

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["senses"][0]["translations"] == ["リンゴ"]

    async def test_direct_lookup_multi_sense_has_distinct_translations(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_MULTI_SENSE_EN_DIRECT_LOOKUP

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="bank",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        # 同じ headword だが、 sense ごとに異なる translations
        assert result["senses"][0]["translations"] == ["銀行"]
        assert result["senses"][1]["translations"] == ["土手", "川岸"]

    async def test_direct_lookup_multi_sense_keeps_same_headword(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_MULTI_SENSE_EN_DIRECT_LOOKUP

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="bank",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["input"] == "bank"
        assert len(result["senses"]) == 2
        # MODE A では全 sense が同じ headword(= user input)
        assert result["senses"][0]["headword"] == "bank"
        assert result["senses"][1]["headword"] == "bank"
        # 意味は異なる
        assert "金融" in result["senses"][0]["meaning"]
        assert "土手" in result["senses"][1]["meaning"]

    async def test_reverse_lookup_returns_multiple_senses_with_target_lang_headwords(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_MULTI_SENSE_JA_REVERSE_LOOKUP

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="retrieval",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["input"] == "retrieval"
        assert len(result["senses"]) == 2

        sense_1, sense_2 = result["senses"]
        assert sense_1["headword"] == "検索"
        assert sense_1["headword_reading"] == "けんさく"
        assert sense_2["headword"] == "回収"
        assert sense_2["headword_reading"] == "かいしゅう"

    async def test_direct_lookup_japanese_word_keeps_input_and_headword_same(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_JA_DIRECT_LOOKUP

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="視察",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        assert result["input"] == "視察"
        assert result["senses"][0]["headword"] == "視察"
        assert result["senses"][0]["headword_reading"] == "しさつ"

    async def test_dictionary_url_uses_user_input(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_MULTI_SENSE_JA_REVERSE_LOOKUP

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="retrieval",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template="https://jisho.org/search/{word}",
        )

        # 主見出しではなくユーザー入力(retrieval)が URL に入る
        assert result["dictionary_url"] == "https://jisho.org/search/retrieval"

    async def test_handles_response_wrapped_in_code_fences(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return f"```json\n{MOCK_SINGLE_SENSE_EN_TARGET}\n```"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)

        result = await word_handler.handle_word(
            word="apple",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template="https://example.com/{word}",
        )

        assert result["senses"][0]["headword"] == "apple"

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

    async def test_falls_back_to_user_word_when_input_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "senses": [{
                    "headword": "apple",
                    "headword_reading": "",
                    "part_of_speech": "noun",
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

        assert result["input"] == "apple"
