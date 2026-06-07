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


class TestExtractUniqueTranslations:
    def test_flattens_translations_across_senses_preserving_order(self):
        senses = [
            {"headword": "bank", "translations": ["銀行"]},
            {"headword": "bank", "translations": ["土手", "川岸"]},
        ]
        assert dispatcher._extract_unique_translations(senses) == ["銀行", "土手", "川岸"]

    def test_dedupes_repeated_translations(self):
        senses = [
            {"headword": "list", "translations": ["上場する", "リストアップする"]},
            {"headword": "go public", "translations": ["上場する"]},
        ]
        assert dispatcher._extract_unique_translations(senses) == [
            "上場する",
            "リストアップする",
        ]

    def test_skips_empty_translations(self):
        senses = [{"headword": "x", "translations": ["", "意味"]}]
        assert dispatcher._extract_unique_translations(senses) == ["意味"]

    def test_missing_translations_key_returns_empty(self):
        senses = [{"headword": "x"}]
        assert dispatcher._extract_unique_translations(senses) == []


class TestSummarizeWordResult:
    def test_mode_a_en_target_uses_translations(self):
        # 英語学習者が英単語を投げる: query が target_lang の script
        senses = [
            {"headword": "complacent", "translations": ["自己満足の", "現状に満足した"]}
        ]
        assert (
            dispatcher._summarize_word_result("complacent", senses, "en")
            == "自己満足の / 現状に満足した"
        )

    def test_mode_b_en_target_uses_headwords(self):
        # 英語学習者が日本語を投げる: query が explanation_lang の script
        senses = [
            {"headword": "list", "translations": ["上場する"]},
            {"headword": "go public", "translations": ["上場する"]},
        ]
        assert (
            dispatcher._summarize_word_result("上場する", senses, "en")
            == "list / go public"
        )

    def test_mode_a_ja_target_uses_translations(self):
        # 日本語学習者が日本語を投げる
        senses = [{"headword": "視察", "translations": ["inspection", "observation"]}]
        assert (
            dispatcher._summarize_word_result("視察", senses, "ja")
            == "inspection / observation"
        )

    def test_mode_b_ja_target_uses_headwords(self):
        # 日本語学習者が英語を投げる
        senses = [
            {"headword": "高さ", "translations": ["height", "altitude"]},
            {"headword": "身長", "translations": ["height"]},
        ]
        assert (
            dispatcher._summarize_word_result("height", senses, "ja") == "高さ / 身長"
        )

    def test_mode_a_empty_translations_yields_empty_string(self):
        # 防御的: translations が空でも例外にせず空文字を返す (anki_card 側でゴミ扱い)
        senses = [{"headword": "asdfg", "translations": []}]
        assert dispatcher._summarize_word_result("asdfg", senses, "en") == ""
