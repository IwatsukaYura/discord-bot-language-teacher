import csv
import io
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from db import query_log, quiz_log
from reports.anki_card import AnkiCard

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_MAX_ITEMS_PER_SECTION = 50
_EMBED_FIELD_MAX = 1024

_ANKI_DECK_LABEL = {
    "en": "Language Teacher EN",
    "ja": "Language Teacher JA",
}


def build_weekly_anki_csv(
    cards: list[AnkiCard],
    target_lang: str,
    start: datetime,
) -> str:
    """Anki Basic note type にそのまま import 可能な 2列 CSV を返す。

    Front 列に target_lang の語 (Mode A の reading は「単語【よみ】」で埋め込み済み)、
    Back 列に explanation_lang の意味。
    """
    deck_label = _ANKI_DECK_LABEL.get(target_lang, "Language Teacher")
    deck_name = f"{deck_label} ({start.strftime('%Y-%m-%d')})"

    buf = io.StringIO()
    buf.write("#separator:Comma\n")
    buf.write("#html:false\n")
    buf.write("#notetype:Basic\n")
    buf.write("#columns:Front,Back\n")
    buf.write(f"#deck:{deck_name}\n")

    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    for card in cards:
        writer.writerow([card.front, card.back])

    return buf.getvalue()


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


def get_report_period(now: datetime) -> tuple[datetime, datetime]:
    """週次レポートの集計期間: 発火時点から遡る 7 日間 (rolling window)。

    例) 土曜09:00 発火 → 前週土曜09:00 〜 当週土曜09:00 の 7 日間。
    DB クエリは半開区間 [start, end) で行うため、終端は now (=次回発火直前) としない。
    """
    return now - timedelta(days=7), now


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
    if item.get("reading"):
        line += f"【{item['reading']}】"
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


def _add_dashboard_fields(
    embed: discord.Embed,
    kind_counts: dict[str, int],
    active_days: int,
    total_days: int,
    quiz_stats: tuple[int, int],
) -> None:
    total = sum(kind_counts.values())
    word = kind_counts.get("word", 0)
    sentence = kind_counts.get("sentence", 0)
    grammar = kind_counts.get("grammar", 0)
    embed.add_field(
        name="📊 質問数",
        value=f"**{total}** 件\n単語 {word} / 文章 {sentence} / 文法 {grammar}",
        inline=True,
    )
    embed.add_field(
        name="📅 学習日数",
        value=f"**{active_days}** / {total_days} 日",
        inline=True,
    )
    answered, correct = quiz_stats
    if answered == 0:
        quiz_value = "未実施"
    else:
        accuracy = round(correct / answered * 100)
        quiz_value = f"**{accuracy}%** ({answered} 問)"
    embed.add_field(
        name="🧪 クイズ正解率",
        value=quiz_value,
        inline=True,
    )


def build_weekly_embed(
    learner_name: str,
    target_lang: str,
    kind_summary: dict[str, list[dict]],
    start: datetime,
    end: datetime,
    kind_counts: dict[str, int] | None = None,
    active_days: int = 0,
    total_days: int = 7,
    quiz_stats: tuple[int, int] = (0, 0),
) -> discord.Embed:
    direction = "EN → JA" if target_lang == "en" else "JA → EN"
    label = "英語学習" if target_lang == "en" else "日本語学習"
    color = discord.Color.blue() if target_lang == "en" else discord.Color.red()
    date_str = f"{start.strftime('%Y-%m-%d')} 〜 {end.strftime('%Y-%m-%d')}"

    embed = discord.Embed(
        title="📚 今週の学習レポート",
        description=f"**{learner_name}** / {label} ({direction})\n{date_str}",
        color=color,
    )

    if kind_counts is not None:
        _add_dashboard_fields(embed, kind_counts, active_days, total_days, quiz_stats)

    for kind, header_label, unit, formatter in _SECTION_CONFIG:
        items = kind_summary.get(kind, [])
        if not items:
            continue
        shown = items[:_MAX_ITEMS_PER_SECTION]
        lines = [formatter(item) for item in shown]
        overflow = len(items) - _MAX_ITEMS_PER_SECTION
        if overflow > 0:
            if kind == "word":
                lines.append(f"… (他 {overflow} 件 — 全件はCSVをダウンロード)")
            else:
                lines.append(f"… (他 {overflow} 件)")
        embed.add_field(
            name=f"{header_label} ({len(items)} {unit})",
            value=_truncate_field("\n".join(lines)),
            inline=False,
        )

    return embed


async def post_weekly_reports(
    client: discord.Client,
    channel_id: int,
    target_lang: str,
    learner_name: str,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> None:
    if now is None:
        now = datetime.now(JST)
    if db_path is None:
        db_path = query_log.DEFAULT_DB_PATH

    start, end = get_report_period(now)
    logs = query_log.get_logs_in_range(start, end, db_path=db_path)
    summary = build_weekly_summary(logs)

    kind_summary = summary.get(target_lang)
    if not kind_summary:
        logger.info("No activity this week for %s; skipping report", target_lang)
        return

    kind_counts = query_log.count_queries_by_kind_in_range(
        target_lang, start, end, db_path=db_path
    )
    active_days = query_log.count_active_days_in_range(
        target_lang, start, end, db_path=db_path
    )
    quiz_stats = quiz_log.get_accuracy_in_range(
        target_lang, start, end, db_path=db_path
    )
    # rolling 7-day window: (end - start) は厳密に 7 日。
    total_days = (end - start).days

    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    embed = build_weekly_embed(
        learner_name=learner_name,
        target_lang=target_lang,
        kind_summary=kind_summary,
        start=start,
        end=end,
        kind_counts=kind_counts,
        active_days=active_days,
        total_days=total_days,
        quiz_stats=quiz_stats,
    )
    # Late import: weekly_view imports from this module, avoid circular dependency.
    from reports.weekly_view import WeeklyCsvView

    view = WeeklyCsvView(target_lang=target_lang, start=start)
    await channel.send(embed=embed, view=view)
    logger.info("Posted weekly report for %s (%s)", learner_name, target_lang)
