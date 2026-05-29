import json

import pytest

from handlers import quiz_handler
from llm import client as llm_client


def _quiz_obj(source_text: str, correct_index: int = 0) -> dict:
    return {
        "source_text": source_text,
        "question_text": "?",
        "choices": ["a", "b", "c", "d"],
        "correct_index": correct_index,
        "explanation": "e",
    }


def _resp(source_text: str, correct_index: int = 0) -> str:
    return json.dumps(_quiz_obj(source_text, correct_index), ensure_ascii=False)


def _arr(*source_texts: str) -> str:
    return json.dumps([_quiz_obj(s) for s in source_texts], ensure_ascii=False)


class FakeGenerate:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    async def __call__(self, system_prompt, user_message):
        self.prompts.append(system_prompt)
        idx = self.calls
        self.calls += 1
        text = self.responses[idx] if idx < len(self.responses) else self.responses[-1]
        return llm_client.LLMResult(text=text, model="test-model", provider="gemini")


class TestGenerateNewQuizDedup:
    async def test_returns_first_when_not_a_duplicate(self, monkeypatch):
        fake = FakeGenerate([_resp("鉛筆")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz(
            history=[], exclusion_list=["付箋"], target_lang="ja", explanation_lang="en",
        )

        assert result["source_text"] == "鉛筆"
        assert result["model_label"] == "test-model"
        assert fake.calls == 1

    async def test_retries_until_non_duplicate(self, monkeypatch):
        fake = FakeGenerate([_resp("付箋"), _resp("鉛筆")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz(
            history=[], exclusion_list=["付箋"], target_lang="ja", explanation_lang="en",
        )

        assert result["source_text"] == "鉛筆"
        assert fake.calls == 2

    async def test_rejected_word_is_fed_into_retry_prompt(self, monkeypatch):
        # "apple" is excluded; model returns the surface variant "Apple" (a normalized
        # duplicate). The retry prompt must explicitly forbid that exact rejected form.
        fake = FakeGenerate([_resp("Apple"), _resp("banana")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        await quiz_handler.generate_new_quiz(
            history=[], exclusion_list=["apple"], target_lang="en", explanation_lang="ja",
        )

        assert "Apple" not in fake.prompts[0]
        assert "Apple" in fake.prompts[1]

    async def test_dedup_is_case_insensitive(self, monkeypatch):
        fake = FakeGenerate([_resp("Apple"), _resp("banana")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz(
            history=[], exclusion_list=["apple"], target_lang="en", explanation_lang="ja",
        )

        assert result["source_text"] == "banana"
        assert fake.calls == 2

    async def test_raises_after_max_attempts_all_duplicate(self, monkeypatch):
        fake = FakeGenerate([_resp("付箋")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        with pytest.raises(ValueError):
            await quiz_handler.generate_new_quiz(
                history=[], exclusion_list=["付箋"], target_lang="ja", explanation_lang="en",
            )

        assert fake.calls == quiz_handler._MAX_NEW_QUIZ_ATTEMPTS


class TestGenerateNewQuizBatch:
    async def test_returns_all_in_one_call_when_distinct(self, monkeypatch):
        fake = FakeGenerate([_arr("a", "b", "c")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=3, history=[], exclusion_list=[], target_lang="en", explanation_lang="ja",
        )

        assert [q["source_text"] for q in result] == ["a", "b", "c"]
        assert all(q["model_label"] == "test-model" for q in result)
        assert fake.calls == 1

    async def test_dedups_within_a_batch(self, monkeypatch):
        # model repeats "a" inside the array; only distinct ones count, so it
        # needs a follow-up call to reach count.
        fake = FakeGenerate([_arr("a", "a", "b"), _arr("c")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=3, history=[], exclusion_list=[], target_lang="en", explanation_lang="ja",
        )

        assert [q["source_text"] for q in result] == ["a", "b", "c"]
        assert fake.calls == 2

    async def test_excludes_listed_words(self, monkeypatch):
        fake = FakeGenerate([_arr("a", "b"), _arr("c")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=2, history=[], exclusion_list=["a"], target_lang="en", explanation_lang="ja",
        )

        assert [q["source_text"] for q in result] == ["b", "c"]
        assert fake.calls == 2

    async def test_caps_calls_and_returns_best_effort_when_short(self, monkeypatch):
        fake = FakeGenerate([_arr("a"), _arr("a")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=3, history=[], exclusion_list=[], target_lang="en", explanation_lang="ja",
        )

        assert [q["source_text"] for q in result] == ["a"]
        assert fake.calls == quiz_handler._MAX_BATCH_ATTEMPTS

    async def test_never_returns_more_than_count(self, monkeypatch):
        fake = FakeGenerate([_arr("a", "b", "c", "d", "e")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=2, history=[], exclusion_list=[], target_lang="en", explanation_lang="ja",
        )

        assert len(result) == 2
        assert fake.calls == 1

    async def test_tolerates_single_object_response(self, monkeypatch):
        fake = FakeGenerate([_resp("a")])
        monkeypatch.setattr(quiz_handler.llm_client, "generate", fake)

        result = await quiz_handler.generate_new_quiz_batch(
            count=1, history=[], exclusion_list=[], target_lang="en", explanation_lang="ja",
        )

        assert [q["source_text"] for q in result] == ["a"]
        assert fake.calls == 1
