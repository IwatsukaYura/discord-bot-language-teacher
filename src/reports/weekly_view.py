import io
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from db import query_log
from reports.anki_card import build_anki_cards
from reports.weekly import build_weekly_anki_csv

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_CUSTOM_ID_PREFIX = "weekly_csv"
_DATE_FORMAT = "%Y-%m-%d"


def build_custom_id(target_lang: str, start: datetime) -> str:
    return f"{_CUSTOM_ID_PREFIX}:{target_lang}:{start.strftime(_DATE_FORMAT)}"


def parse_custom_id(custom_id: str) -> tuple[str, datetime] | None:
    """custom_id を (target_lang, start_datetime) にパース。週次CSV由来でなければ None。"""
    if not custom_id.startswith(f"{_CUSTOM_ID_PREFIX}:"):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    target_lang = parts[1]
    try:
        start = datetime.strptime(parts[2], _DATE_FORMAT).replace(tzinfo=JST)
    except ValueError:
        return None
    return target_lang, start


class WeeklyCsvView(discord.ui.View):
    """週次レポートに添えるCSVエクスポートボタン。

    custom_id ベースで Bot 再起動を跨いで反応するため callback は付けず、
    main の on_interaction 経由で処理する。timeout=None で永続。
    """

    def __init__(self, target_lang: str, start: datetime):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="📥 単語をCSVでエクスポート（Anki用）",
                custom_id=build_custom_id(target_lang, start),
            )
        )


async def handle_weekly_csv_click(
    interaction: discord.Interaction,
    target_lang: str,
    start: datetime,
    db_path: Path | None = None,
) -> None:
    if db_path is None:
        db_path = query_log.DEFAULT_DB_PATH

    end = start + timedelta(days=7)
    logs = query_log.get_logs_in_range(start, end, db_path=db_path)
    cards = build_anki_cards(logs, target_lang)

    if not cards:
        await interaction.response.send_message(
            "この週には単語の記録がありませんでした。", ephemeral=True
        )
        return

    csv_text = build_weekly_anki_csv(cards, target_lang, start)
    buf = io.BytesIO(csv_text.encode("utf-8"))
    filename = f"weekly-words-{target_lang}-{start.strftime(_DATE_FORMAT)}.csv"
    await interaction.response.send_message(
        file=discord.File(buf, filename=filename),
        ephemeral=True,
    )
    logger.info(
        "Sent weekly CSV (lang=%s, start=%s, cards=%d)",
        target_lang, start.strftime(_DATE_FORMAT), len(cards),
    )
