import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from db import query_log, quiz_log

JST = ZoneInfo("Asia/Tokyo")


def _insert_query(
    db_path: Path,
    discord_user_id: str,
    target_lang: str,
    query_text: str,
    result_summary: str,
) -> None:
    query_log.init_db(db_path)
    query_log.insert_query_log(
        kind="word",
        target_lang=target_lang,
        discord_user_id=discord_user_id,
        discord_user_name="alice",
        query_text=query_text,
        result_summary=result_summary,
        db_path=db_path,
    )


def _insert_quiz_raw(
    db_path: Path,
    discord_user_id: str,
    target_lang: str,
    delivered_at_iso: str,
    answered_at_iso: str | None = None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO quiz_log "
            "(discord_user_id, target_lang, kind, mode, source_text, question_text, "
            "choices_json, correct_index, explanation, delivered_at, answered_at) "
            "VALUES (?, ?, 'word', 'new', 's', 'q', '[]', 0, 'e', ?, ?)",
            (discord_user_id, target_lang, delivered_at_iso, answered_at_iso),
        )


def _insert_quiz_full(
    db_path: Path,
    discord_user_id: str,
    target_lang: str,
    delivered_at_iso: str,
    is_correct: int | None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO quiz_log "
            "(discord_user_id, target_lang, kind, mode, source_text, question_text, "
            "choices_json, correct_index, explanation, delivered_at, is_correct) "
            "VALUES (?, ?, 'word', 'new', 's', 'q', '[]', 0, 'e', ?, ?)",
            (discord_user_id, target_lang, delivered_at_iso, is_correct),
        )


class TestInitDb:
    def test_creates_quiz_addon_table(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_addon'"
            )
            assert cursor.fetchone() is not None

    def test_is_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        quiz_log.init_db(db_path)


class TestAddonAllowance:
    def test_has_used_addon_today_is_false_when_no_record(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        assert quiz_log.has_used_addon_today("1", "en", db_path=db_path) is False

    def test_mark_then_has_used_returns_true(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        quiz_log.mark_addon_used("1", "en", db_path=db_path)

        assert quiz_log.has_used_addon_today("1", "en", db_path=db_path) is True

    def test_usage_resets_on_a_different_day(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        # Simulate a usage record left from a past day
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO quiz_addon (discord_user_id, target_lang, used_date) "
                "VALUES ('1', 'en', '2020-01-01')"
            )

        assert quiz_log.has_used_addon_today("1", "en", db_path=db_path) is False

    def test_usage_is_scoped_per_user(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        quiz_log.mark_addon_used("1", "en", db_path=db_path)

        assert quiz_log.has_used_addon_today("2", "en", db_path=db_path) is False

    def test_usage_is_scoped_per_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        quiz_log.mark_addon_used("1", "en", db_path=db_path)

        assert quiz_log.has_used_addon_today("1", "ja", db_path=db_path) is False

    def test_mark_is_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        quiz_log.mark_addon_used("1", "en", db_path=db_path)
        quiz_log.mark_addon_used("1", "en", db_path=db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM quiz_addon WHERE discord_user_id='1' AND target_lang='en'"
            )
            assert cursor.fetchone()[0] == 1

    def test_clear_restores_allowance(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        quiz_log.mark_addon_used("1", "en", db_path=db_path)

        quiz_log.clear_addon_used("1", "en", db_path=db_path)

        assert quiz_log.has_used_addon_today("1", "en", db_path=db_path) is False

    def test_clear_is_scoped_per_user_and_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        quiz_log.mark_addon_used("1", "en", db_path=db_path)
        quiz_log.mark_addon_used("2", "en", db_path=db_path)

        quiz_log.clear_addon_used("1", "en", db_path=db_path)

        assert quiz_log.has_used_addon_today("1", "en", db_path=db_path) is False
        assert quiz_log.has_used_addon_today("2", "en", db_path=db_path) is True


class TestCountUnansweredToday:
    def test_returns_zero_when_no_quizzes(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        assert quiz_log.count_unanswered_today("1", "en", db_path=db_path) == 0

    def test_counts_today_unanswered_quizzes(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        now = datetime.now(JST).isoformat()
        _insert_quiz_raw(db_path, "1", "en", now)
        _insert_quiz_raw(db_path, "1", "en", now)

        assert quiz_log.count_unanswered_today("1", "en", db_path=db_path) == 2

    def test_excludes_answered_quizzes(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        now = datetime.now(JST).isoformat()
        _insert_quiz_raw(db_path, "1", "en", now, answered_at_iso=now)
        _insert_quiz_raw(db_path, "1", "en", now)

        assert quiz_log.count_unanswered_today("1", "en", db_path=db_path) == 1

    def test_excludes_quizzes_from_other_days(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        yesterday = (datetime.now(JST) - timedelta(days=1)).isoformat()
        _insert_quiz_raw(db_path, "1", "en", yesterday)

        assert quiz_log.count_unanswered_today("1", "en", db_path=db_path) == 0

    def test_is_scoped_per_user_and_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        now = datetime.now(JST).isoformat()
        _insert_quiz_raw(db_path, "1", "en", now)
        _insert_quiz_raw(db_path, "2", "en", now)
        _insert_quiz_raw(db_path, "1", "ja", now)

        assert quiz_log.count_unanswered_today("1", "en", db_path=db_path) == 1


class TestGetAccuracyInRange:
    def test_counts_only_answered_quizzes(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        _insert_quiz_full(db_path, "1", "en", "2026-05-15T10:00:00+09:00", is_correct=1)
        _insert_quiz_full(db_path, "1", "en", "2026-05-15T11:00:00+09:00", is_correct=0)
        _insert_quiz_full(db_path, "1", "en", "2026-05-15T12:00:00+09:00", is_correct=None)

        answered, correct = quiz_log.get_accuracy_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert answered == 2
        assert correct == 1

    def test_returns_zero_when_no_records(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)

        answered, correct = quiz_log.get_accuracy_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert answered == 0
        assert correct == 0

    def test_excludes_other_target_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        _insert_quiz_full(db_path, "1", "ja", "2026-05-15T10:00:00+09:00", is_correct=1)

        answered, correct = quiz_log.get_accuracy_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert answered == 0
        assert correct == 0

    def test_excludes_outside_range(self, tmp_path):
        db_path = tmp_path / "test.db"
        quiz_log.init_db(db_path)
        _insert_quiz_full(db_path, "1", "en", "2026-05-10T10:00:00+09:00", is_correct=1)
        _insert_quiz_full(db_path, "1", "en", "2026-05-20T10:00:00+09:00", is_correct=1)

        answered, correct = quiz_log.get_accuracy_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert answered == 0
        assert correct == 0


class TestGetStudiedTargetLangWords:
    def test_mode_a_japanese_query_returns_query_text(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "視察", "inspection")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == ["視察"]

    def test_mode_b_english_query_extracts_translations_from_summary(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "height", "高さ / 身長")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == ["高さ", "身長"]

    def test_mode_b_single_headword_summary(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "apple", "りんご")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == ["りんご"]

    def test_mode_b_empty_summary_yields_nothing(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "height", "")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == []

    def test_mode_b_summary_with_only_english_yields_nothing(self, tmp_path):
        # Defensive: LLM mistakenly returned English in result_summary for a JA bot
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "height", "tall / high")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == []

    def test_en_target_mode_a_keeps_english_query(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "en", "apple", "りんご")

        words = quiz_log.get_studied_target_lang_words("1", "en", db_path=db_path)
        assert words == ["apple"]

    def test_en_target_mode_b_extracts_english_from_summary(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "en", "視察", "inspection / observation")

        words = quiz_log.get_studied_target_lang_words("1", "en", db_path=db_path)
        assert words == ["inspection", "observation"]

    def test_combines_mode_a_and_mode_b_rows(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "視察", "inspection")
        _insert_query(db_path, "1", "ja", "height", "高さ / 身長")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert set(words) == {"視察", "高さ", "身長"}

    def test_deduplicates_across_rows(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "視察", "inspection")
        _insert_query(db_path, "1", "ja", "視察", "inspection")
        _insert_query(db_path, "1", "ja", "inspection", "視察")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == ["視察"]

    def test_excludes_other_users(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "視察", "inspection")
        _insert_query(db_path, "2", "ja", "高さ", "height")

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == ["視察"]

    def test_excludes_other_target_langs(self, tmp_path):
        db_path = tmp_path / "test.db"
        _insert_query(db_path, "1", "ja", "視察", "inspection")
        _insert_query(db_path, "1", "en", "apple", "りんご")

        ja_words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        en_words = quiz_log.get_studied_target_lang_words("1", "en", db_path=db_path)
        assert ja_words == ["視察"]
        assert en_words == ["apple"]

    def test_excludes_non_word_kinds(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        query_log.insert_query_log(
            kind="sentence", target_lang="ja",
            discord_user_id="1", discord_user_name="a",
            query_text="これは何ですか", result_summary="What is this?",
            db_path=db_path,
        )
        query_log.insert_query_log(
            kind="grammar", target_lang="ja",
            discord_user_id="1", discord_user_name="a",
            query_text="What does 〜てしまう mean?", result_summary="〜てしまう",
            db_path=db_path,
        )

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == []

    def test_returns_empty_for_user_with_no_history(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        words = quiz_log.get_studied_target_lang_words("1", "ja", db_path=db_path)
        assert words == []
