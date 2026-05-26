import json

import pytest

from handlers import grammar_handler
from llm import gemini_client


MOCK_JA_GRAMMAR_RESPONSE = json.dumps({
    "topic": "〜てしまう",
    "explanation": "The construction 〜てしまう has two main meanings: completion and regret.",
    "examples": [
        {"source": "宿題を全部やってしまった。", "translation": "I finished all the homework."},
        {"source": "寝坊してしまった。", "translation": "I overslept (and feel bad about it)."},
    ],
    "related": "In casual speech, often becomes 〜ちゃう.",
})

MOCK_EN_GRAMMAR_RESPONSE = json.dumps({
    "topic": "would have p.p.",
    "explanation": "would have + 過去分詞は仮定法過去完了で、過去の事実と反対の仮定を表します。",
    "examples": [
        {"source": "I would have helped you.", "translation": "君を助けていたのに。"},
    ],
    "related": "",
})


class TestStripCodeFences:
    def test_removes_json_labeled_fence(self):
        assert grammar_handler._strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_passes_through_when_no_fence(self):
        assert grammar_handler._strip_code_fences('{"a":1}') == '{"a":1}'


class TestHandleGrammar:
    async def test_returns_structured_dict_for_japanese_grammar_question(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_JA_GRAMMAR_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "What does 〜てしまう mean?", target_lang="ja", explanation_lang="en",
        )

        assert result["topic"] == "〜てしまう"
        assert result["target_lang"] == "ja"
        assert result["explanation_lang"] == "en"
        assert "completion and regret" in result["explanation"]
        assert len(result["examples"]) == 2
        assert result["examples"][0]["source"] == "宿題を全部やってしまった。"
        assert result["related"] == "In casual speech, often becomes 〜ちゃう."

    async def test_returns_structured_dict_for_english_grammar_question(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return MOCK_EN_GRAMMAR_RESPONSE

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "would have p.p.の使い方", target_lang="en", explanation_lang="ja",
        )

        assert result["topic"] == "would have p.p."
        assert result["target_lang"] == "en"
        assert result["explanation_lang"] == "ja"
        assert "仮定法過去完了" in result["explanation"]
        assert len(result["examples"]) == 1
        assert result["related"] == ""

    async def test_handles_response_wrapped_in_code_fences(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return f"```json\n{MOCK_JA_GRAMMAR_RESPONSE}\n```"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "anything", target_lang="ja", explanation_lang="en",
        )
        assert result["topic"] == "〜てしまう"

    async def test_raises_value_error_on_invalid_json(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return "this is not json"

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        with pytest.raises(ValueError, match="Invalid JSON from Gemini"):
            await grammar_handler.handle_grammar(
                "anything", target_lang="en", explanation_lang="ja",
            )

    async def test_defaults_related_to_empty_string_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "topic": "X",
                "explanation": "...",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "anything", target_lang="en", explanation_lang="ja",
        )
        assert result["related"] == ""

    async def test_defaults_examples_to_empty_list_when_missing(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "topic": "X",
                "explanation": "...",
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "anything", target_lang="en", explanation_lang="ja",
        )
        assert result["examples"] == []

    async def test_target_and_explanation_lang_come_from_caller_not_response(self, monkeypatch):
        async def fake_generate(system_prompt, user_prompt):
            return json.dumps({
                "topic": "X",
                "explanation": "...",
                "examples": [],
            })

        monkeypatch.setattr(gemini_client, "generate", fake_generate)
        result = await grammar_handler.handle_grammar(
            "anything", target_lang="ja", explanation_lang="en",
        )
        assert result["target_lang"] == "ja"
        assert result["explanation_lang"] == "en"
