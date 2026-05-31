from reports.anki_card import AnkiCard, build_anki_cards


def _log(
    kind: str = "word",
    target_lang: str = "ja",
    query_text: str = "",
    result_summary: str = "",
    reading: str = "",
) -> dict:
    return {
        "kind": kind,
        "target_lang": target_lang,
        "query_text": query_text,
        "result_summary": result_summary,
        "reading": reading,
    }


class TestModeA:
    def test_japanese_query_passes_through(self):
        logs = [_log(query_text="視察", result_summary="inspection", reading="しさつ")]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="視察【しさつ】", back="inspection")]

    def test_reading_omitted_when_empty(self):
        logs = [_log(query_text="ひらがな", result_summary="hiragana")]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="ひらがな", back="hiragana")]

    def test_english_query_passes_through_for_en_target(self):
        logs = [_log(target_lang="en", query_text="apple", result_summary="リンゴ")]
        cards = build_anki_cards(logs, "en")
        assert cards == [AnkiCard(front="apple", back="リンゴ")]


class TestModeB:
    def test_english_query_to_ja_target_uses_summary_as_front(self):
        logs = [_log(query_text="apple", result_summary="リンゴ")]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="リンゴ", back="apple")]

    def test_multi_headword_summary_explodes_to_multiple_cards(self):
        logs = [_log(query_text="height", result_summary="高さ / 身長")]
        cards = build_anki_cards(logs, "ja")
        assert cards == [
            AnkiCard(front="高さ", back="height"),
            AnkiCard(front="身長", back="height"),
        ]

    def test_japanese_query_to_en_target_uses_summary_as_front(self):
        logs = [_log(target_lang="en", query_text="検索", result_summary="search / retrieval")]
        cards = build_anki_cards(logs, "en")
        assert cards == [
            AnkiCard(front="search", back="検索"),
            AnkiCard(front="retrieval", back="検索"),
        ]

    def test_mode_b_skips_headwords_not_matching_target_script(self):
        # Defensive: result_summary が混在していた場合、target_lang に一致するものだけ採用
        logs = [_log(query_text="apple", result_summary="リンゴ / apple")]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="リンゴ", back="apple")]


class TestGarbageFiltering:
    def test_garbage_summary_excluded_japanese(self):
        logs = [_log(query_text="asdfg", result_summary="該当なし")]
        cards = build_anki_cards(logs, "ja")
        assert cards == []

    def test_garbage_summary_excluded_english(self):
        logs = [_log(query_text="asdfg", result_summary="無意味")]
        cards = build_anki_cards(logs, "ja")
        assert cards == []

    def test_garbage_no_match_excluded_case_insensitive(self):
        logs = [_log(query_text="asdfg", result_summary="No Match")]
        cards = build_anki_cards(logs, "ja")
        assert cards == []

    def test_empty_summary_excluded(self):
        logs = [_log(query_text="asdfg", result_summary="")]
        cards = build_anki_cards(logs, "ja")
        assert cards == []

    def test_whitespace_only_summary_excluded(self):
        logs = [_log(query_text="asdfg", result_summary="   ")]
        cards = build_anki_cards(logs, "ja")
        assert cards == []


class TestFiltering:
    def test_skips_non_word_kinds(self):
        logs = [
            _log(kind="sentence", query_text="これは何", result_summary="What is this"),
            _log(kind="grammar", query_text="〜てしまう", result_summary="completion aspect"),
        ]
        cards = build_anki_cards(logs, "ja")
        assert cards == []

    def test_skips_other_target_langs(self):
        logs = [
            _log(target_lang="en", query_text="apple", result_summary="リンゴ"),
            _log(target_lang="ja", query_text="視察", result_summary="inspection"),
        ]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="視察", back="inspection")]


class TestDeduplication:
    def test_identical_mode_a_entries_deduped(self):
        logs = [
            _log(query_text="視察", result_summary="inspection", reading="しさつ"),
            _log(query_text="視察", result_summary="inspection", reading="しさつ"),
        ]
        cards = build_anki_cards(logs, "ja")
        assert cards == [AnkiCard(front="視察【しさつ】", back="inspection")]

    def test_mode_a_and_mode_b_yielding_same_front_keep_first(self):
        # Mode A: 高さ -> "tall / height" として記録
        # Mode B: height -> "高さ / 身長" として記録 → 高さがダブる
        logs = [
            _log(query_text="高さ", result_summary="tall / height"),
            _log(query_text="height", result_summary="高さ / 身長"),
        ]
        cards = build_anki_cards(logs, "ja")
        assert cards == [
            AnkiCard(front="高さ", back="tall / height"),  # first occurrence wins
            AnkiCard(front="身長", back="height"),
        ]


class TestEmpty:
    def test_empty_logs_returns_empty_list(self):
        assert build_anki_cards([], "ja") == []
