import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from db import query_log

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_MAX_ITEMS_PER_SECTION = 50
_EMBED_FIELD_MAX = 1024


def build_weekly_summary(logs: list[dict]) -> dict[str, dict[str, list[dict]]]:
    groups: dict[str, dict[str, dict[str, dict]]] = {}

    for log in logs:
        lang = log["target_lang"]
        kind = log["kind"]
        text = log["query_text"]

        if lang not in groups:
            groups[lang] = {}
        if kind not in groups[lang]:
            groups[lang][kind] = {}

        if text not in groups[lang][kind]:
            groups[lang][kind][text] = {
                "text": text,
                "summary": log.get("result_summary") or "",
                "reading": log.get("reading") or "",
                "count": 0,
            }

        groups[lang][kind][text]["count"] += 1

    return {
        lang: {
            kind: sorted(items.values(), key=lambda x: -x["count"])
            for kind, items in kind_map.items()
        }
        for lang, kind_map in groups.items()
    }


def get_current_week_range(now: datetime) -> tuple[datetime, datetime]:
    days_since_monday = now.weekday()
    monday = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday, now


def _format_count_suffix(count: int) -> str:
    return f" (×{count})" if count > 1 else ""


def _format_word_line(item: dict) -> str:
    line = f"• {item['text']}"
    if item.get("reading"):
        line += f"【{item['reading']}】"
    if item["summary"]:
        line += f" — {item['summary']}"
    line += _format_count_suffix(item["count"])
    return line


def _format_sentence_line(item: dict) -> str:
    line = f"• {item['text']}"
    if item["summary"]:
        line += f" — {item['summary']}"
    line += _format_count_suffix(item["count"])
    return line


def _format_grammar_line(item: dict) -> str:
    topic = item["summary"] or item["text"]
    return f"• {topic}{_format_count_suffix(item['count'])}"


def _truncate_field(text: str) -> str:
    if len(text) <= _EMBED_FIELD_MAX:
        return text
    return text[: _EMBED_FIELD_MAX - 3] + "..."


_SECTION_CONFIG = [
    ("word", "📘 調べた単語", "語", _format_word_line),
    ("sentence", "📝 翻訳した文章", "件", _format_sentence_line),
    ("grammar", "📚 学んだ文法", "件", _format_grammar_line),
]


def build_weekly_embed(
    learner_name: str,
    target_lang: str,
    kind_summary: dict[str, list[dict]],
    start: datetime,
    end: datetime,
) -> discord.Embed:
    direction = "EN → JA" if target_lang == "en" else "JA → EN"
    label = "英語学習" if target_lang == "en" else "日本語学習"
    color = discord.Color.blue() if target_lang == "en" else discord.Color.red()
    date_str = f"{start.strftime('%Y-%m-%d')} 〜 {end.strftime('%Y-%m-%d')}"

    embed = discord.Embed(
        title="📚 今週の学習サマリ",
        description=f"**{learner_name}** / {label} ({direction})\n{date_str}",
        color=color,
    )

    for kind, header_label, unit, formatter in _SECTION_CONFIG:
        items = kind_summary.get(kind, [])
        if not items:
            continue
        shown = items[:_MAX_ITEMS_PER_SECTION]
        lines = [formatter(item) for item in shown]
        if len(items) > _MAX_ITEMS_PER_SECTION:
            lines.append(f"… (他 {len(items) - _MAX_ITEMS_PER_SECTION} 件)")
        embed.add_field(
            name=f"{header_label} ({len(items)} {unit})",
            value=_truncate_field("\n".join(lines)),
            inline=False,
        )

    return embed


def _get_learner_names() -> dict[str, str]:
    return {
        "en": os.getenv("EN_LEARNER_NAME", "English learner"),
        "ja": os.getenv("JA_LEARNER_NAME", "Japanese learner"),
    }


async def post_weekly_reports(
    client: discord.Client,
    channel_id: int,
    now: datetime | None = None,
    db_path: Path | None = None,
    learner_names: dict[str, str] | None = None,
) -> None:
    if now is None:
        now = datetime.now(JST)
    if db_path is None:
        db_path = query_log.DEFAULT_DB_PATH
    if learner_names is None:
        learner_names = _get_learner_names()

    start, end = get_current_week_range(now)
    logs = query_log.get_logs_in_range(start, end, db_path=db_path)
    summary = build_weekly_summary(logs)

    if not summary:
        logger.info("No activity this week; skipping report posting")
        return

    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)

    for target_lang, kind_summary in summary.items():
        learner_name = learner_names.get(target_lang, f"{target_lang} learner")
        embed = build_weekly_embed(learner_name, target_lang, kind_summary, start, end)
        await channel.send(embed=embed)
        logger.info("Posted weekly report for %s (%s)", learner_name, target_lang)
