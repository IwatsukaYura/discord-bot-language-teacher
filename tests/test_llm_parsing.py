"""llm.parsing のテスト。

各ハンドラに重複していた _strip_code_fences のテストをここに統合した。
"""

import pytest

from llm.parsing import parse_json_response, strip_code_fences


class TestStripCodeFences:
    def test_removes_json_labeled_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert strip_code_fences(text) == '{"a": 1}'

    def test_removes_plain_fence(self):
        text = '```\n{"a": 1}\n```'
        assert strip_code_fences(text) == '{"a": 1}'

    def test_passes_through_when_no_fence(self):
        text = '{"a": 1}'
        assert strip_code_fences(text) == '{"a": 1}'

    def test_strips_leading_and_trailing_whitespace(self):
        text = '   {"a": 1}   '
        assert strip_code_fences(text) == '{"a": 1}'


class TestParseJsonResponse:
    def test_parses_fenced_json_object(self):
        assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

    def test_parses_bare_json_array(self):
        assert parse_json_response('[{"a": 1}]') == [{"a": 1}]

    def test_raises_value_error_on_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON from Gemini"):
            parse_json_response("not json at all")
