from lib.script import matches_target_lang


class TestMatchesTargetLangJa:
    def test_pure_hiragana_matches_ja(self):
        assert matches_target_lang("おはよう", "ja") is True

    def test_pure_katakana_matches_ja(self):
        assert matches_target_lang("コーヒー", "ja") is True

    def test_pure_kanji_matches_ja(self):
        assert matches_target_lang("高", "ja") is True

    def test_kanji_with_okurigana_matches_ja(self):
        assert matches_target_lang("高さ", "ja") is True

    def test_compound_kanji_matches_ja(self):
        assert matches_target_lang("身長", "ja") is True

    def test_english_word_does_not_match_ja(self):
        assert matches_target_lang("height", "ja") is False

    def test_mixed_ascii_and_kana_matches_ja(self):
        # 「PCを買う」のような外来略語まじり
        assert matches_target_lang("PCを買う", "ja") is True


class TestMatchesTargetLangEn:
    def test_single_english_word_matches_en(self):
        assert matches_target_lang("height", "en") is True

    def test_multi_word_english_matches_en(self):
        assert matches_target_lang("pick up", "en") is True

    def test_japanese_does_not_match_en(self):
        assert matches_target_lang("高さ", "en") is False

    def test_mixed_japanese_and_ascii_does_not_match_en(self):
        assert matches_target_lang("appleりんご", "en") is False

    def test_apostrophe_word_matches_en(self):
        assert matches_target_lang("don't", "en") is True


class TestMatchesEdgeCases:
    def test_empty_string_returns_false(self):
        assert matches_target_lang("", "ja") is False
        assert matches_target_lang("", "en") is False

    def test_whitespace_only_returns_false(self):
        assert matches_target_lang("   ", "ja") is False
        assert matches_target_lang("   ", "en") is False

    def test_punctuation_only_returns_false(self):
        assert matches_target_lang("???", "en") is False
        assert matches_target_lang("???", "ja") is False

    def test_digits_only_returns_false(self):
        assert matches_target_lang("123", "en") is False
        assert matches_target_lang("123", "ja") is False

    def test_unknown_target_lang_returns_false(self):
        assert matches_target_lang("hello", "fr") is False
        assert matches_target_lang("おはよう", "zh") is False
