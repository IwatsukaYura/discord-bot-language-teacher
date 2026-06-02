import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from db import query_log
from reports import weekly
from reports.weekly import JST


def _log(user: str, lang: str, kind: str, text: str, summary: str | None = "x",
         reading: str = "") -> dict:
    return {
        "kind": kind,
        "discord_user_name": user,
        "target_lang": lang,
        "query_text": text,
        "result_summary": summary,
        "reading": reading,
    }


class TestBuildWeeklySummary:
    def test_returns_empty_dict_for_empty_logs(self):
        assert weekly.build_weekly_summary([]) == {}

    def test_single_word_log_creates_nested_entry(self):
        logs = [_log("alice", "en", "word", "apple", "りんご")]
        result = weekly.build_weekly_summary(logs)
        assert result == {
            "en": {
                "word": [{"text": "apple", "summary": "りんご", "reading": "", "count": 1}]
            }
        }

    def test_aggregates_duplicate_words_with_count(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "word", "apple", "りんご"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result == {
            "en": {
                "word": [{"text": "apple", "summary": "りんご", "reading": "", "count": 3}]
            }
        }

    def test_merges_logs_from_different_users_for_same_target_lang(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("bob", "en", "word", "banana", "バナナ"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert "en" in result
        assert len(result) == 1
        words = result["en"]["word"]
        assert {w["text"] for w in words} == {"apple", "banana"}

    def test_separates_different_target_langs(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "ja", "word", "林檎", "apple"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert set(result.keys()) == {"en", "ja"}

    def test_merges_same_word_asked_by_different_users(self):
        logs = [
            _log("alice", "ja", "word", "視察", "inspection", reading="しさつ"),
            _log("bob", "ja", "word", "視察", "inspection", reading="しさつ"),
        ]
        result = weekly.build_weekly_summary(logs)
        item = result["ja"]["word"][0]
        assert item["text"] == "視察"
        assert item["count"] == 2

    def test_separates_different_kinds_within_same_target_lang(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "sentence", "Could you?", "できますか?"),
            _log("alice", "en", "grammar", "would have", "would have p.p."),
        ]
        result = weekly.build_weekly_summary(logs)
        assert set(result["en"].keys()) == {"word", "sentence", "grammar"}

    def test_sorts_items_by_count_descending(self):
        logs = [
            _log("alice", "en", "word", "apple"),
            _log("alice", "en", "word", "banana"),
            _log("alice", "en", "word", "banana"),
            _log("alice", "en", "word", "cherry"),
            _log("alice", "en", "word", "cherry"),
            _log("alice", "en", "word", "cherry"),
        ]
        result = weekly.build_weekly_summary(logs)
        words = result["en"]["word"]
        assert [w["text"] for w in words] == ["cherry", "banana", "apple"]
        assert [w["count"] for w in words] == [3, 2, 1]

    def test_preserves_first_summary_on_duplicates(self):
        logs = [
            _log("alice", "en", "word", "bank", "銀行"),
            _log("alice", "en", "word", "bank", "土手"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["summary"] == "銀行"

    def test_handles_none_summary_as_empty_string(self):
        logs = [_log("alice", "en", "word", "apple", None)]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["summary"] == ""

    def test_preserves_reading_field_for_japanese_words(self):
        logs = [
            _log("alice", "ja", "word", "視察", "inspection", reading="しさつ"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["ja"]["word"][0]["reading"] == "しさつ"

    def test_reading_defaults_to_empty_when_missing(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["reading"] == ""


class TestBuildWeeklyAnkiCsv:
    def _start(self) -> datetime:
        return datetime.fromisoformat("2026-05-25T00:00:00+09:00")

    def test_includes_anki_header_lines(self):
        from reports.anki_card import AnkiCard
        csv_text = weekly.build_weekly_anki_csv(
            cards=[],
            target_lang="en",
            start=self._start(),
        )
        lines = csv_text.splitlines()
        assert lines[0] == "#separator:Comma"
        assert lines[1] == "#html:false"
        assert lines[2] == "#notetype:Basic"
        assert lines[3] == "#columns:Front,Back"
        assert lines[4] == "#deck:Language Teacher EN (2026-05-25)"

    def test_writes_front_back_per_card(self):
        from reports.anki_card import AnkiCard
        cards = [
            AnkiCard(front="apple", back="りんご"),
            AnkiCard(front="視察【しさつ】", back="inspection"),
        ]
        csv_text = weekly.build_weekly_anki_csv(
            cards=cards,
            target_lang="ja",
            start=self._start(),
        )
        lines = csv_text.splitlines()
        assert lines[4] == "#deck:Language Teacher JA (2026-05-25)"
        assert lines[5] == "apple,りんご"
        assert lines[6] == "視察【しさつ】,inspection"

    def test_quotes_back_with_comma(self):
        from reports.anki_card import AnkiCard
        cards = [AnkiCard(front="endeavor", back="努力, 試み")]
        csv_text = weekly.build_weekly_anki_csv(
            cards=cards,
            target_lang="en",
            start=self._start(),
        )
        data_line = csv_text.splitlines()[5]
        assert data_line == 'endeavor,"努力, 試み"'

    def test_escapes_double_quotes_in_back(self):
        from reports.anki_card import AnkiCard
        cards = [AnkiCard(front="scare", back='say "boo"')]
        csv_text = weekly.build_weekly_anki_csv(
            cards=cards,
            target_lang="en",
            start=self._start(),
        )
        data_line = csv_text.splitlines()[5]
        assert data_line == 'scare,"say ""boo"""'

    def test_returns_only_headers_when_no_cards(self):
        csv_text = weekly.build_weekly_anki_csv(
            cards=[],
            target_lang="en",
            start=self._start(),
        )
        assert csv_text.splitlines() == [
            "#separator:Comma",
            "#html:false",
            "#notetype:Basic",
            "#columns:Front,Back",
            "#deck:Language Teacher EN (2026-05-25)",
        ]

    def test_unknown_target_lang_falls_back_to_generic_deck(self):
        csv_text = weekly.build_weekly_anki_csv(
            cards=[],
            target_lang="fr",
            start=self._start(),
        )
        assert csv_text.splitlines()[4] == "#deck:Language Teacher (2026-05-25)"


def _insert_raw(db_path: Path, kind: str, target_lang: str, query_text: str,
                result_summary: str, queried_at_iso: str,
                is_correct: int | None = None) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO query_log "
            "(kind, target_lang, discord_user_id, discord_user_name, "
            "query_text, result_summary, reading, queried_at) "
            "VALUES (?, ?, '1', 'alice', ?, ?, '', ?)",
            (kind, target_lang, query_text, result_summary, queried_at_iso),
        )


def _insert_quiz(db_path: Path, target_lang: str, delivered_at: str,
                 is_correct: int | None) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO quiz_log "
            "(discord_user_id, target_lang, kind, mode, source_text, question_text, "
            "choices_json, correct_index, explanation, delivered_at, is_correct) "
            "VALUES ('1', ?, 'word', 'new', 's', 'q', '[]', 0, 'e', ?, ?)",
            (target_lang, delivered_at, is_correct),
        )


class TestPostWeeklyReports:
    async def test_skips_when_no_activity(self, tmp_path):
        from db import quiz_log
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        quiz_log.init_db(db_path)

        channel = MagicMock()
        channel.send = AsyncMock()
        client = MagicMock()
        client.get_channel = MagicMock(return_value=channel)

        await weekly.post_weekly_reports(
            client=client,
            channel_id=123,
            target_lang="en",
            learner_name="alice",
            now=datetime(2026, 5, 24, 21, 0, tzinfo=JST),
            db_path=db_path,
        )

        channel.send.assert_not_awaited()

    async def test_posts_embed_and_view_when_activity_exists(self, tmp_path):
        from db import quiz_log
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        quiz_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "apple", "りんご",
                    "2026-05-19T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "banana", "バナナ",
                    "2026-05-20T10:00:00+09:00")
        _insert_raw(db_path, "sentence", "en", "Hello", "こんにちは",
                    "2026-05-21T10:00:00+09:00")
        _insert_quiz(db_path, "en", "2026-05-22T10:00:00+09:00", is_correct=1)
        _insert_quiz(db_path, "en", "2026-05-22T11:00:00+09:00", is_correct=0)

        channel = MagicMock()
        channel.send = AsyncMock()
        client = MagicMock()
        client.get_channel = MagicMock(return_value=channel)

        await weekly.post_weekly_reports(
            client=client,
            channel_id=123,
            target_lang="en",
            learner_name="alice",
            now=datetime(2026, 5, 24, 21, 0, tzinfo=JST),
            db_path=db_path,
        )

        channel.send.assert_awaited_once()
        kwargs = channel.send.await_args.kwargs
        embed = kwargs["embed"]
        view = kwargs["view"]

        # Dashboard rendered with correct totals
        names = [f.name for f in embed.fields]
        assert any("質問数" in n for n in names)
        q_field = next(f for f in embed.fields if "質問数" in f.name)
        assert "3" in q_field.value  # total queries
        assert "単語 2" in q_field.value
        assert "文章 1" in q_field.value

        # Active days counts query_log activity dates only:
        # 2026-05-19, 20, 21 = 3 distinct dates (quiz on 22 does not count).
        # Rolling window: 2026-05-17 21:00 〜 2026-05-24 21:00 → all 3 dates inside.
        days_field = next(f for f in embed.fields if "学習日数" in f.name)
        assert "3" in days_field.value
        assert "7" in days_field.value  # rolling 7-day window

        # Quiz: 2 answered, 1 correct = 50%
        quiz_field = next(f for f in embed.fields if "クイズ" in f.name)
        assert "50%" in quiz_field.value

        # View has the CSV button
        from reports.weekly_view import WeeklyCsvView
        assert isinstance(view, WeeklyCsvView)
        # Rolling window start: 2026-05-24 21:00 - 7 days = 2026-05-17
        assert view.children[0].custom_id == "weekly_csv:en:2026-05-17"

    async def test_uses_only_target_lang_data(self, tmp_path):
        from db import quiz_log
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        quiz_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "apple", "りんご",
                    "2026-05-19T10:00:00+09:00")
        _insert_raw(db_path, "word", "ja", "視察", "inspection",
                    "2026-05-19T11:00:00+09:00")

        channel = MagicMock()
        channel.send = AsyncMock()
        client = MagicMock()
        client.get_channel = MagicMock(return_value=channel)

        await weekly.post_weekly_reports(
            client=client,
            channel_id=123,
            target_lang="en",
            learner_name="alice",
            now=datetime(2026, 5, 24, 21, 0, tzinfo=JST),
            db_path=db_path,
        )

        embed = channel.send.await_args.kwargs["embed"]
        q_field = next(f for f in embed.fields if "質問数" in f.name)
        assert "単語 1" in q_field.value
