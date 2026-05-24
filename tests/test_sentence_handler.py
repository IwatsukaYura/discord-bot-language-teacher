import json

import pytest

from handlers import sentence_handler
from llm import gemini_client


MOCK_VALID_RESPONSE = json.dumps({
    "translation": "駅まで迎えに来てもらえますか?",
    "literal_translation": "あなたは駅で私をピックアップしてもらえますか?",
    "key_points": [
        "pick someone up = 車などで誰かを迎えに行く",
        "Could you 〜? は丁寧な依頼",
    ],
})


class TestBuildSystemPrompt:
    def test_for_english_input_mentions_english_and_japanese(self):
        prompt = sentence_handler._build_system_prompt("en", "ja")
        assert "English" in prompt
        assert "Japanese" in prompt

    def test_for_japanese_input_mentions_japanese_and_english(self):
        prompt = sentence_handler._build_system_prompt("ja", "en")
        assert "Japanese" in prompt
        assert "English" in prompt


class TestStripCodeFences:
    def test_removes_json_labeled_fence(self):
        assert sentence_handler._strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_passes_through_when_no_fence(self):
        assert sentence_handler._strip_code_fences('{"a":1}') == '{"a":1}'


class TestHandleSentence:
    async def test_returns_structured_dict_on_valid_response(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_VALID_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await sentence_handler.handle_sentence(
            text="Could you pick me up at the station?",
            target_lang="en",
            explanation_lang="ja",
        )

        assert result["source_text"] == "Could you pick me up at the station?"
        assert result["translation"] == "駅まで迎えに来てもらえますか?"
        assert result["literal_translation"] == "あなたは駅で私をピックアップしてもらえますか?"
        assert len(result["key_points"]) == 2
        assert result["key_points"][0] == "pick someone up = 車などで誰かを迎えに行く"

    async def test_handles_response_wrapped_in_code_fences(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return f"```json\n{MOCK_VALID_RESPONSE}\n```"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await sentence_handler.handle_sentence(
            text="anything",
            target_lang="en",
            explanation_lang="ja",
        )
        assert result["translation"] == "駅まで迎えに来てもらえますか?"

    async def test_raises_value_error_on_invalid_json(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "this is not json"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        with pytest.raises(ValueError, match="Invalid JSON from Gemini"):
            await sentence_handler.handle_sentence(
                text="anything",
                target_lang="en",
                explanation_lang="ja",
            )

    async def test_defaults_literal_translation_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({"translation": "test", "key_points": []})

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await sentence_handler.handle_sentence(
            text="anything",
            target_lang="en",
            explanation_lang="ja",
        )
        assert result["literal_translation"] == ""

    async def test_defaults_key_points_to_empty_list_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({"translation": "test"})

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await sentence_handler.handle_sentence(
            text="anything",
            target_lang="en",
            explanation_lang="ja",
        )
        assert result["key_points"] == []
