import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from db import quiz_log

JST = ZoneInfo("Asia/Tokyo")


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
