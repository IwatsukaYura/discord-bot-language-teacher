import pytest

from quiz import poster


class TestAddonCustomId:
    @pytest.mark.parametrize("count", [0, 1, 2, 3])
    def test_round_trip(self, count):
        custom_id = poster.build_addon_custom_id("12345", "en", count)
        assert poster.parse_addon_custom_id(custom_id) == ("12345", "en", count)

    def test_returns_none_for_non_addon_prefix(self):
        assert poster.parse_addon_custom_id("quiz:1:2") is None

    def test_returns_none_for_wrong_part_count(self):
        assert poster.parse_addon_custom_id("quizadd:12345:en") is None

    def test_returns_none_for_non_integer_count(self):
        assert poster.parse_addon_custom_id("quizadd:12345:en:x") is None

    def test_returns_none_for_out_of_range_count(self):
        assert poster.parse_addon_custom_id("quizadd:12345:en:5") is None


class TestParserIsolation:
    def test_quiz_parser_rejects_addon_id(self):
        assert poster.parse_custom_id("quizadd:12345:en:2") is None

    def test_addon_parser_rejects_quiz_id(self):
        assert poster.parse_addon_custom_id("quiz:1:2") is None


class TestAddonView:
    def test_builds_four_buttons(self):
        view = poster.AddonView(user_id="12345", target_lang="en", explanation_lang="ja")
        assert len(view.children) == 4

    def test_buttons_cover_counts_0_to_3(self):
        view = poster.AddonView(user_id="12345", target_lang="en", explanation_lang="ja")
        counts = set()
        for child in view.children:
            parsed = poster.parse_addon_custom_id(child.custom_id)
            assert parsed is not None
            counts.add(parsed[2])
        assert counts == {0, 1, 2, 3}


class TestBuildQuizEmbedAddon:
    def test_addon_title_ja(self):
        embed = poster.build_quiz_embed(
            source_text="apple", question_text="?", target_lang="en",
            explanation_lang="ja", mode="new", position=(1, 3), addon=True,
        )
        assert "追加" in embed.title

    def test_addon_title_en(self):
        embed = poster.build_quiz_embed(
            source_text="りんご", question_text="?", target_lang="ja",
            explanation_lang="en", mode="new", position=(1, 3), addon=True,
        )
        assert "Bonus" in embed.title

    def test_default_title_is_daily(self):
        embed = poster.build_quiz_embed(
            source_text="apple", question_text="?", target_lang="en",
            explanation_lang="ja", mode="new", position=(1, 2),
        )
        assert "今日" in embed.title
