"""lib.lang のテスト。"""

from lib.lang import explanation_lang_for, lang_names


class TestLangNames:
    def test_en_target_ja_explanation(self):
        assert lang_names("en", "ja") == ("English", "Japanese")

    def test_ja_target_en_explanation(self):
        assert lang_names("ja", "en") == ("Japanese", "English")


class TestExplanationLangFor:
    def test_en_learner_gets_japanese_explanation(self):
        assert explanation_lang_for("en") == "ja"

    def test_ja_learner_gets_english_explanation(self):
        assert explanation_lang_for("ja") == "en"
