from lib import dispatcher


class TestExtractUniqueHeadwords:
    def test_returns_single_headword_for_single_sense(self):
        senses = [{"headword": "apple"}]
        assert dispatcher._extract_unique_headwords(senses) == ["apple"]

    def test_dedupes_same_headword_across_senses(self):
        senses = [{"headword": "bank"}, {"headword": "bank"}]
        assert dispatcher._extract_unique_headwords(senses) == ["bank"]

    def test_preserves_order_of_first_appearance(self):
        senses = [
            {"headword": "検索"},
            {"headword": "回収"},
            {"headword": "検索"},
        ]
        assert dispatcher._extract_unique_headwords(senses) == ["検索", "回収"]


class TestSummarizeHeadwords:
    def test_joins_unique_headwords_with_slash(self):
        senses = [
            {"headword": "検索"},
            {"headword": "回収"},
        ]
        assert dispatcher._summarize_headwords(senses) == "検索 / 回収"

    def test_dedupes_for_mode_a_same_headword(self):
        senses = [
            {"headword": "bank"},
            {"headword": "bank"},
        ]
        assert dispatcher._summarize_headwords(senses) == "bank"
