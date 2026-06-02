import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from db import query_log
from reports import weekly_view
from reports.weekly_view import JST


def _insert_raw(db_path: Path, kind: str, target_lang: str, query_text: str,
                result_summary: str, queried_at_iso: str, reading: str = "") -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO query_log "
            "(kind, target_lang, discord_user_id, discord_user_name, "
            "query_text, result_summary, reading, queried_at) "
            "VALUES (?, ?, '1', 'alice', ?, ?, ?, ?)",
            (kind, target_lang, query_text, result_summary, reading, queried_at_iso),
        )


class TestBuildCustomId:
    def test_returns_prefixed_string(self):
        start = datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        assert weekly_view.build_custom_id("en", start) == "weekly_csv:en:2026-05-18"


class TestParseCustomId:
    def test_returns_lang_and_start_for_valid_id(self):
        result = weekly_view.parse_custom_id("weekly_csv:en:2026-05-18")
        assert result is not None
        target_lang, start = result
        assert target_lang == "en"
        assert start == datetime(2026, 5, 18, 0, 0, tzinfo=JST)

    def test_returns_none_for_other_prefix(self):
        assert weekly_view.parse_custom_id("quiz:1:0") is None
        assert weekly_view.parse_custom_id("quizadd:1:en:1") is None

    def test_returns_none_for_wrong_field_count(self):
        assert weekly_view.parse_custom_id("weekly_csv:en") is None
        assert weekly_view.parse_custom_id("weekly_csv:en:2026-05-18:extra") is None

    def test_returns_none_for_invalid_date(self):
        assert weekly_view.parse_custom_id("weekly_csv:en:not-a-date") is None
        assert weekly_view.parse_custom_id("weekly_csv:en:2026-13-99") is None

    def test_roundtrips_build_and_parse(self):
        start = datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        custom_id = weekly_view.build_custom_id("ja", start)
        target_lang, parsed_start = weekly_view.parse_custom_id(custom_id)
        assert target_lang == "ja"
        assert parsed_start == start


class TestWeeklyCsvView:
    def test_contains_single_button_with_custom_id(self):
        start = datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        view = weekly_view.WeeklyCsvView(target_lang="en", start=start)

        assert len(view.children) == 1
        button = view.children[0]
        assert isinstance(button, discord.ui.Button)
        assert button.custom_id == "weekly_csv:en:2026-05-18"
        assert "CSV" in button.label

    def test_is_persistent_view(self):
        start = datetime(2026, 5, 18, 0, 0, tzinfo=JST)
        view = weekly_view.WeeklyCsvView(target_lang="en", start=start)
        assert view.timeout is None


class TestHandleWeeklyCsvClick:
    async def test_sends_csv_file_when_words_exist(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "apple", "りんご",
                    "2026-05-19T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "banana", "バナナ",
                    "2026-05-20T10:00:00+09:00")

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await weekly_view.handle_weekly_csv_click(
            interaction=interaction,
            target_lang="en",
            start=datetime(2026, 5, 18, 0, 0, tzinfo=JST),
            db_path=db_path,
        )

        interaction.response.send_message.assert_awaited_once()
        kwargs = interaction.response.send_message.await_args.kwargs
        assert kwargs["ephemeral"] is True
        file = kwargs["file"]
        assert isinstance(file, discord.File)
        assert file.filename == "weekly-words-en-2026-05-18.csv"

        # Verify CSV content
        file.fp.seek(0)
        body = file.fp.read().decode("utf-8")
        assert "#columns:Front,Back" in body
        assert "#notetype:Basic" in body
        # Mode A: query_text(EN) matches en script → front=query_text, back=summary
        assert "apple,りんご" in body
        assert "banana,バナナ" in body

    async def test_replies_with_text_when_no_words(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await weekly_view.handle_weekly_csv_click(
            interaction=interaction,
            target_lang="en",
            start=datetime(2026, 5, 18, 0, 0, tzinfo=JST),
            db_path=db_path,
        )

        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        assert kwargs["ephemeral"] is True
        # First positional arg is the message text
        assert "記録がありません" in args[0]
        assert "file" not in kwargs

    async def test_only_includes_word_kind_for_target_lang(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "apple", "りんご",
                    "2026-05-19T10:00:00+09:00")
        _insert_raw(db_path, "sentence", "en", "Hello", "こんにちは",
                    "2026-05-19T11:00:00+09:00")
        _insert_raw(db_path, "word", "ja", "視察", "inspection",
                    "2026-05-19T12:00:00+09:00", reading="しさつ")

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await weekly_view.handle_weekly_csv_click(
            interaction=interaction,
            target_lang="en",
            start=datetime(2026, 5, 18, 0, 0, tzinfo=JST),
            db_path=db_path,
        )

        kwargs = interaction.response.send_message.await_args.kwargs
        file = kwargs["file"]
        file.fp.seek(0)
        body = file.fp.read().decode("utf-8")
        assert "apple" in body
        assert "Hello" not in body
        assert "視察" not in body

    async def test_excludes_words_outside_week_range(self, tmp_path):
        db_path = tmp_path / "test.db"
        query_log.init_db(db_path)
        _insert_raw(db_path, "word", "en", "before", "x",
                    "2026-05-10T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "inside", "y",
                    "2026-05-19T10:00:00+09:00")
        _insert_raw(db_path, "word", "en", "after", "z",
                    "2026-05-30T10:00:00+09:00")

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await weekly_view.handle_weekly_csv_click(
            interaction=interaction,
            target_lang="en",
            start=datetime(2026, 5, 18, 0, 0, tzinfo=JST),
            db_path=db_path,
        )

        kwargs = interaction.response.send_message.await_args.kwargs
        file = kwargs["file"]
        file.fp.seek(0)
        body = file.fp.read().decode("utf-8")
        assert "inside" in body
        assert "before" not in body
        assert "after" not in body
