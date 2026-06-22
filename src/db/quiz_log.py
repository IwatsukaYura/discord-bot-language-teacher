import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from db.query_log import DEFAULT_DB_PATH
from lib.script import matches_target_lang

# dispatcher._summarize_headwords が " / " で結合する result_summary を分解するための区切り。
# フォーマットを変える場合は dispatcher 側と合わせて変更する。
_HEADWORD_SEPARATOR = " / "

JST = ZoneInfo("Asia/Tokyo")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_user_id    TEXT    NOT NULL,
    target_lang        TEXT    NOT NULL,
    kind               TEXT    NOT NULL,
    mode               TEXT    NOT NULL,
    source_text        TEXT    NOT NULL,
    question_text      TEXT    NOT NULL,
    choices_json       TEXT    NOT NULL,
    correct_index      INTEGER NOT NULL,
    explanation        TEXT    NOT NULL,
    message_id         TEXT,
    delivered_at       TEXT    NOT NULL,
    answered_at        TEXT,
    user_answer_index  INTEGER,
    is_correct         INTEGER
);

CREATE INDEX IF NOT EXISTS idx_quiz_user_delivered ON quiz_log(discord_user_id, delivered_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_message        ON quiz_log(message_id);
CREATE INDEX IF NOT EXISTS idx_quiz_user_source    ON quiz_log(discord_user_id, source_text);

CREATE TABLE IF NOT EXISTS quiz_addon (
    discord_user_id  TEXT NOT NULL,
    target_lang      TEXT NOT NULL,
    used_date        TEXT NOT NULL,
    UNIQUE(discord_user_id, target_lang, used_date)
);
"""


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def insert_quiz(
    discord_user_id: str,
    target_lang: str,
    kind: str,
    mode: str,
    source_text: str,
    question_text: str,
    choices: Sequence[str],
    correct_index: int,
    explanation: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    delivered_at = datetime.now(JST).isoformat()
    choices_json = json.dumps(choices, ensure_ascii=False)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO quiz_log "
            "(discord_user_id, target_lang, kind, mode, source_text, "
            "question_text, choices_json, correct_index, explanation, delivered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                discord_user_id, target_lang, kind, mode, source_text,
                question_text, choices_json, correct_index, explanation, delivered_at,
            ),
        )
        return cursor.lastrowid


def set_message_id(quiz_id: int, message_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE quiz_log SET message_id = ? WHERE id = ?",
            (message_id, quiz_id),
        )


def record_answer(
    quiz_id: int,
    user_answer_index: int,
    is_correct: bool,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    answered_at = datetime.now(JST).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE quiz_log "
            "SET answered_at = ?, user_answer_index = ?, is_correct = ? "
            "WHERE id = ?",
            (answered_at, user_answer_index, 1 if is_correct else 0, quiz_id),
        )


def get_quiz_by_id(quiz_id: int, db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM quiz_log WHERE id = ?", (quiz_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["choices"] = json.loads(d.pop("choices_json"))
        return d


def get_recent_quiz_source_texts(
    discord_user_id: str,
    target_lang: str,
    days: int = 14,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    """直近 days 日に出題した source_text の一覧(復習除外用)。"""
    cutoff = (datetime.now(JST) - timedelta(days=days)).isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT DISTINCT source_text FROM quiz_log "
            "WHERE discord_user_id = ? AND target_lang = ? AND delivered_at >= ?",
            (discord_user_id, target_lang, cutoff),
        )
        return [row[0] for row in cursor.fetchall()]


def get_all_quiz_source_texts(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    """全期間で過去出題した source_text の一覧(新出除外用)。"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT DISTINCT source_text FROM quiz_log "
            "WHERE discord_user_id = ? AND target_lang = ?",
            (discord_user_id, target_lang),
        )
        return [row[0] for row in cursor.fetchall()]


def get_studied_target_lang_words(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    """学習者が word kind で過去調べた語のうち、target_lang のスクリプトで書かれたものを返す。

    Mode A (query_text が target_lang script に一致): その query_text を採用。
    Mode B (不一致: 例 height を JA-bot に問い合わせた): result_summary を _HEADWORD_SEPARATOR
    で分解し、target_lang script に一致する見出し語(例 高さ / 身長)を採用。

    復習候補と新出除外の両方の用途で使う。重複は排除、出現順は SQL の返却順。
    """
    pool: list[str] = []
    seen: set[str] = set()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT query_text, result_summary FROM query_log "
            "WHERE discord_user_id = ? AND target_lang = ? AND kind = 'word'",
            (discord_user_id, target_lang),
        )
        for query_text, result_summary in cursor.fetchall():
            if matches_target_lang(query_text, target_lang):
                if query_text not in seen:
                    seen.add(query_text)
                    pool.append(query_text)
                continue
            if not result_summary:
                continue
            for headword in result_summary.split(_HEADWORD_SEPARATOR):
                headword = headword.strip()
                if (
                    headword
                    and matches_target_lang(headword, target_lang)
                    and headword not in seen
                ):
                    seen.add(headword)
                    pool.append(headword)

    return pool


def count_unanswered_today(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """今日(JST)配信され、まだ未回答のクイズ件数。追加プロンプト表示判定に使う。"""
    now = datetime.now(JST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM quiz_log "
            "WHERE discord_user_id = ? AND target_lang = ? "
            "AND delivered_at >= ? AND delivered_at < ? AND answered_at IS NULL",
            (discord_user_id, target_lang, today_start.isoformat(), tomorrow_start.isoformat()),
        )
        return cursor.fetchone()[0]


def has_used_addon_today(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """今日(JST)すでに追加クイズ枠を消費済みかどうか。"""
    today = datetime.now(JST).date().isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM quiz_addon "
            "WHERE discord_user_id = ? AND target_lang = ? AND used_date = ? LIMIT 1",
            (discord_user_id, target_lang, today),
        )
        return cursor.fetchone() is not None


def mark_addon_used(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """今日(JST)の追加クイズ枠を消費済みにする。同日重複呼び出しは無視。"""
    today = datetime.now(JST).date().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO quiz_addon (discord_user_id, target_lang, used_date) "
            "VALUES (?, ?, ?)",
            (discord_user_id, target_lang, today),
        )


def clear_addon_used(
    discord_user_id: str,
    target_lang: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """今日(JST)の追加クイズ枠の消費を取り消す(生成失敗時の返却用)。"""
    today = datetime.now(JST).date().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM quiz_addon "
            "WHERE discord_user_id = ? AND target_lang = ? AND used_date = ?",
            (discord_user_id, target_lang, today),
        )


def get_accuracy_in_range(
    target_lang: str,
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[int, int]:
    """期間内に配信され回答済みのクイズについて (answered, correct) を返す。
    answered は回答済み件数(分母)、correct はそのうち正解した件数(分子)。"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(is_correct), 0) FROM quiz_log "
            "WHERE target_lang = ? "
            "AND delivered_at >= ? AND delivered_at < ? "
            "AND is_correct IS NOT NULL",
            (target_lang, start.isoformat(), end.isoformat()),
        )
        answered, correct = cursor.fetchone()
        return answered, correct


def get_recent_query_history(
    discord_user_id: str,
    target_lang: str,
    limit: int = 30,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    """学習者の直近 N 件 query_text(新出問題のレベル参照プロンプト用、時系列降順)。query_log 参照。"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT query_text FROM query_log "
            "WHERE discord_user_id = ? AND target_lang = ? "
            "ORDER BY queried_at DESC LIMIT ?",
            (discord_user_id, target_lang, limit),
        )
        return [row[0] for row in cursor.fetchall()]
