import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from db import query_log


def _insert_raw(db_path: Path, kind: str, target_lang: str, user_id: str, user_name: str,
                query_text: str, result_summary: str, queried_at_iso: str,
                reading: str = "") -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO query_log "
            "(kind, target_lang, discord_user_id, discord_user_name, query_text, result_summary, reading, queried_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, target_lang, user_id, user_name, query_text, result_summary, reading, queried_at_iso),
        )


class TestInitDb:
    def test_creates_query_log_table(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='query_log'"
            )
            assert cursor.fetchone() is not None

    def test_is_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        query_log.init_db(db_path)

    def test_creates_parent_directory_if_missing(self, tmp_path):
        db_path = tmp_path / "nested" / "dir" / "test.db"
        query_log.init_db(db_path)
        assert db_path.exists()

    def test_migrates_old_schema_by_adding_reading_column(self, tmp_path):
        db_path = tmp_path / "test.db"
        # Simulate an old DB without the reading column
        with sqlite3.connect(db_path) as conn:
            conn.executescript("""
                CREATE TABLE query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    discord_user_id TEXT NOT NULL,
                    discord_user_name TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    result_summary TEXT,
                    queried_at TEXT NOT NULL
                );
            """)
            conn.execute(
                "INSERT INTO query_log "
                "(kind, target_lang, discord_user_id, discord_user_name, query_text, result_summary, queried_at) "
                "VALUES ('word', 'en', '1', 'alice', 'apple', 'りんご', '2026-05-15T10:00:00+09:00')"
            )

        query_log.init_db(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(query_log)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "reading" in columns

            cursor = conn.execute("SELECT query_text, reading FROM query_log")
            row = cursor.fetchone()
            assert row[0] == "apple"
            assert row[1] is None or row[1] == ""


class TestInsertQueryLog:
    def test_inserts_word_kind(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="word",
            target_lang="en",
            discord_user_id="123",
            discord_user_name="alice",
            query_text="apple",
            result_summary="りんご",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT kind, target_lang, discord_user_id, discord_user_name, query_text, result_summary "
                "FROM query_log"
            )
            row = cursor.fetchone()
            assert row == ("word", "en", "123", "alice", "apple", "りんご")

    def test_stores_reading_field_for_japanese_kanji(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="word",
            target_lang="ja",
            discord_user_id="1",
            discord_user_name="alice",
            query_text="視察",
            result_summary="inspection",
            reading="しさつ",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT reading FROM query_log")
            assert cursor.fetchone()[0] == "しさつ"

    def test_reading_defaults_to_empty_string(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="word",
            target_lang="en",
            discord_user_id="1",
            discord_user_name="alice",
            query_text="apple",
            result_summary="りんご",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT reading FROM query_log")
            assert cursor.fetchone()[0] == ""

    def test_inserts_sentence_kind(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="sentence",
            target_lang="en",
            discord_user_id="123",
            discord_user_name="alice",
            query_text="Could you pick me up?",
            result_summary="駅まで迎えに来てもらえますか?",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT kind, query_text FROM query_log")
            row = cursor.fetchone()
            assert row[0] == "sentence"
            assert row[1] == "Could you pick me up?"

    def test_inserts_grammar_kind(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="grammar",
            target_lang="ja",
            discord_user_id="123",
            discord_user_name="alice",
            query_text="What does 〜てしまう mean?",
            result_summary="〜てしまう",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT kind, result_summary FROM query_log")
            row = cursor.fetchone()
            assert row == ("grammar", "〜てしまう")

    def test_stamps_queried_at_with_timezone_aware_iso(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        query_log.insert_query_log(
            kind="word",
            target_lang="en",
            discord_user_id="1",
            discord_user_name="a",
            query_text="w",
            result_summary="t",
            db_path=db_path,
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT queried_at FROM query_log")
            queried_at_str = cursor.fetchone()[0]

        parsed = datetime.fromisoformat(queried_at_str)
        assert parsed.tzinfo is not None


class TestGetLogsInRange:
    def test_returns_records_with_kind_field(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "alice", "apple", "りんご",
                    "2026-05-15T10:00:00+09:00")

        results = query_log.get_logs_in_range(
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert len(results) == 1
        assert results[0]["kind"] == "word"
        assert results[0]["query_text"] == "apple"
        assert results[0]["result_summary"] == "りんご"
        assert results[0]["reading"] == ""

    def test_returns_reading_field(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "ja", "1", "alice", "視察", "inspection",
                    "2026-05-15T10:00:00+09:00", reading="しさつ")

        results = query_log.get_logs_in_range(
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert results[0]["reading"] == "しさつ"

    def test_excludes_records_outside_range(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "before", "x",
                    "2026-05-10T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "1", "a", "after", "y",
                    "2026-05-20T10:00:00+09:00")

        results = query_log.get_logs_in_range(
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert results == []

    def test_orders_by_queried_at_ascending(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "later", "x",
                    "2026-05-15T15:00:00+09:00")
        _insert_raw(db_path, "word", "en", "1", "a", "earlier", "y",
                    "2026-05-15T10:00:00+09:00")

        results = query_log.get_logs_in_range(
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert [r["query_text"] for r in results] == ["earlier", "later"]

    def test_returns_records_of_all_kinds(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "apple", "りんご",
                    "2026-05-15T10:00:00+09:00")
        _insert_raw(db_path, "sentence", "en", "1", "a", "Could you...", "迎えに...",
                    "2026-05-15T11:00:00+09:00")
        _insert_raw(db_path, "grammar", "en", "1", "a", "would have p.p.", "would have p.p.",
                    "2026-05-15T12:00:00+09:00")

        results = query_log.get_logs_in_range(
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        kinds = [r["kind"] for r in results]
        assert kinds == ["word", "sentence", "grammar"]


class TestCountQueriesByKindInRange:
    def test_returns_counts_grouped_by_kind(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "apple", "x",
                    "2026-05-15T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "1", "a", "banana", "y",
                    "2026-05-15T11:00:00+09:00")
        _insert_raw(db_path, "sentence", "en", "1", "a", "Hello", "z",
                    "2026-05-15T12:00:00+09:00")

        counts = query_log.count_queries_by_kind_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert counts == {"word": 2, "sentence": 1}

    def test_excludes_other_target_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "apple", "x",
                    "2026-05-15T10:00:00+09:00")
        _insert_raw(db_path, "word", "ja", "1", "a", "視察", "y",
                    "2026-05-15T11:00:00+09:00")

        counts = query_log.count_queries_by_kind_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert counts == {"word": 1}

    def test_returns_empty_dict_when_no_records(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        counts = query_log.count_queries_by_kind_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert counts == {}


class TestCountActiveDaysInRange:
    def test_counts_distinct_calendar_days(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "1", "a", "apple", "x",
                    "2026-05-15T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "1", "a", "banana", "y",
                    "2026-05-15T20:00:00+09:00")
        _insert_raw(db_path, "word", "en", "1", "a", "cherry", "z",
                    "2026-05-17T10:00:00+09:00")

        active = query_log.count_active_days_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-18T00:00:00+09:00"),
            db_path=db_path,
        )

        assert active == 2

    def test_returns_zero_when_no_records(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        active = query_log.count_active_days_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert active == 0

    def test_excludes_other_target_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "ja", "1", "a", "視察", "y",
                    "2026-05-15T10:00:00+09:00")

        active = query_log.count_active_days_in_range(
            target_lang="en",
            start=datetime.fromisoformat("2026-05-14T00:00:00+09:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+09:00"),
            db_path=db_path,
        )

        assert active == 0
