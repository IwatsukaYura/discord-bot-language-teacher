from datetime import datetime

import discord
import pytest

from reports import weekly
from reports.weekly import JST


def _item(text: str, summary: str, count: int = 1, reading: str = "") -> dict:
    return {"text": text, "summary": summary, "count": count, "reading": reading}


class TestGetCurrentWeekRange:
    def test_when_now_is_sunday_start_is_monday_of_same_week(self):
        now = datetime(2026, 5, 24, 21, 0, tzinfo=JST)
        start, end = weekly.get_current_week_range(now)
        assert start == datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        assert end == now

    def test_when_now_is_monday_start_is_same_day_midnight(self):
        now = datetime(2026, 5, 18, 9, 30, tzinfo=JST)
        start, end = weekly.get_current_week_range(now)
        assert start == datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        assert end == now

    def test_when_now_is_wednesday_start_is_monday_of_same_week(self):
        now = datetime(2026, 5, 20, 15, 0, tzinfo=JST)
        start, end = weekly.get_current_week_range(now)
        assert start == datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        assert end == now


class TestBuildWeeklyEmbed:
    _START = datetime(2026, 5, 18, 0, 0, tzinfo=JST)
    _END = datetime(2026, 5, 24, 21, 0, tzinfo=JST)

    def test_title_contains_summary_label(self):
        embed = weekly.build_weekly_embed(
            learner_name="alice",
            target_lang="en",
            kind_summary={"word": [_item("apple", "りんご")]},
            start=self._START,
            end=self._END,
        )
        assert "今週の学習サマリ" in embed.title

    def test_description_contains_user_label_and_date_range(self):
        embed = weekly.build_weekly_embed(
            learner_name="alice",
            target_lang="en",
            kind_summary={"word": [_item("apple", "りんご")]},
            start=self._START,
            end=self._END,
        )
        assert "alice" in embed.description
        assert "英語学習" in embed.description
        assert "2026-05-18" in embed.description
        assert "2026-05-24" in embed.description

    def test_color_is_blue_for_en_target(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={"word": [_item("x", "y")]},
            start=self._START, end=self._END,
        )
        assert embed.color == discord.Color.blue()

    def test_color_is_red_for_ja_target(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="ja",
            kind_summary={"word": [_item("x", "y")]},
            start=self._START, end=self._END,
        )
        assert embed.color == discord.Color.red()

    def test_word_section_shows_text_summary_and_count(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={"word": [_item("apple", "りんご", count=3)]},
            start=self._START, end=self._END,
        )
        word_field = next(f for f in embed.fields if "単語" in f.name)
        assert "apple" in word_field.value
        assert "りんご" in word_field.value
        assert "×3" in word_field.value

    def test_word_section_omits_count_when_single(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={"word": [_item("apple", "りんご", count=1)]},
            start=self._START, end=self._END,
        )
        word_field = next(f for f in embed.fields if "単語" in f.name)
        assert "×" not in word_field.value

    def test_skips_kinds_with_no_items(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={"word": [_item("apple", "りんご")]},
            start=self._START, end=self._END,
        )
        field_names = [f.name for f in embed.fields]
        assert any("単語" in n for n in field_names)
        assert not any("文章" in n for n in field_names)
        assert not any("文法" in n for n in field_names)

    def test_includes_all_three_sections_when_present(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={
                "word": [_item("apple", "りんご")],
                "sentence": [_item("Could you?", "できますか?")],
                "grammar": [_item("What is ...", "would have p.p.")],
            },
            start=self._START, end=self._END,
        )
        field_names = [f.name for f in embed.fields]
        assert any("単語" in n for n in field_names)
        assert any("文章" in n for n in field_names)
        assert any("文法" in n for n in field_names)

    def test_grammar_section_shows_topic_not_raw_question(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="ja",
            kind_summary={
                "grammar": [_item("What does 〜てしまう mean?", "〜てしまう")]
            },
            start=self._START, end=self._END,
        )
        grammar_field = next(f for f in embed.fields if "文法" in f.name)
        assert "〜てしまう" in grammar_field.value
        assert "What does" not in grammar_field.value

    def test_section_header_includes_count(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={
                "word": [_item("apple", "りんご"), _item("banana", "バナナ")],
            },
            start=self._START, end=self._END,
        )
        word_field = next(f for f in embed.fields if "単語" in f.name)
        assert "2" in word_field.name

    def test_word_line_shows_reading_for_kanji(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="ja",
            kind_summary={
                "word": [_item("視察", "inspection", reading="しさつ")],
            },
            start=self._START, end=self._END,
        )
        word_field = next(f for f in embed.fields if "単語" in f.name)
        assert "視察" in word_field.value
        assert "しさつ" in word_field.value
        assert "【しさつ】" in word_field.value

    def test_word_line_omits_reading_when_empty(self):
        embed = weekly.build_weekly_embed(
            learner_name="a", target_lang="en",
            kind_summary={
                "word": [_item("apple", "りんご", reading="")],
            },
            start=self._START, end=self._END,
        )
        word_field = next(f for f in embed.fields if "単語" in f.name)
        assert "【" not in word_field.value
