import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
DEFAULT_DB_PATH = Path("data/language_teacher.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    discord_user_id TEXT NOT NULL,
    discord_user_name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    result_summary TEXT,
    reading TEXT,
    queried_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_log_queried_at ON query_log(queried_at);
CREATE INDEX IF NOT EXISTS idx_query_log_user_kind ON query_log(discord_user_id, target_lang, kind);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("PRAGMA table_info(query_log)")
    columns = {row[1] for row in cursor.fetchall()}
    if "reading" not in columns:
        conn.execute("ALTER TABLE query_log ADD COLUMN reading TEXT")


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def insert_query_log(
    kind: str,
    target_lang: str,
    discord_user_id: str,
    discord_user_name: str,
    query_text: str,
    result_summary: str,
    reading: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    queried_at = datetime.now(JST).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO query_log "
            "(kind, target_lang, discord_user_id, discord_user_name, query_text, result_summary, reading, queried_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, target_lang, discord_user_id, discord_user_name, query_text, result_summary, reading, queried_at),
        )


def get_logs_in_range(
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT kind, target_lang, discord_user_id, discord_user_name, "
            "query_text, result_summary, reading, queried_at "
            "FROM query_log "
            "WHERE queried_at >= ? AND queried_at < ? "
            "ORDER BY queried_at ASC",
            (start.isoformat(), end.isoformat()),
        )
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("reading") is None:
                d["reading"] = ""
            rows.append(d)
        return rows


def count_queries_by_kind_in_range(
    target_lang: str,
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT kind, COUNT(*) FROM query_log "
            "WHERE target_lang = ? AND queried_at >= ? AND queried_at < ? "
            "GROUP BY kind",
            (target_lang, start.isoformat(), end.isoformat()),
        )
        return {kind: count for kind, count in cursor.fetchall()}


def count_active_days_in_range(
    target_lang: str,
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT substr(queried_at, 1, 10)) FROM query_log "
            "WHERE target_lang = ? AND queried_at >= ? AND queried_at < ?",
            (target_lang, start.isoformat(), end.isoformat()),
        )
        return cursor.fetchone()[0]
