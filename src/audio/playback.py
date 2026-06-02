import asyncio
import io
import logging
import re
from typing import Final

import discord

from lib import tts

logger = logging.getLogger(__name__)

_CUSTOM_ID_PREFIX: Final[str] = "tts"
_SUPPORTED_LANGS: Final[frozenset[str]] = frozenset({"en", "ja"})
_MAX_BUTTONS_PER_ROW: Final[int] = 5  # Discord ActionRow 上限
_FILENAME_UNSAFE: Final[re.Pattern[str]] = re.compile(r"\W+", re.UNICODE)


def _build_custom_id(lang: str, headword: str) -> str:
    return f"{_CUSTOM_ID_PREFIX}:{lang}:{headword}"


def parse_custom_id(custom_id: str) -> tuple[str, str] | None:
    """custom_id が 'tts:<lang>:<headword>' なら (lang, headword) を返す。

    maxsplit=2 にしているので headword 側に ':' が含まれていても保持される。
    """
    parts = custom_id.split(":", 2)
    if len(parts) != 3 or parts[0] != _CUSTOM_ID_PREFIX:
        return None
    _, lang, headword = parts
    if lang not in _SUPPORTED_LANGS or not headword:
        return None
    return lang, headword


def _safe_filename_stem(headword: str) -> str:
    """Discord 添付ファイル名向けに headword をサニタイズ。

    Python 3 の `\\w` は Unicode マッチなので日本語などは保持される。
    全文字が記号類だった場合のみ 'audio' にフォールバック。
    """
    base = _FILENAME_UNSAFE.sub("_", headword).strip("_")
    return base if base else "audio"


def build_audio_view(headwords: list[str], lang: str) -> discord.ui.View | None:
    """ユニーク headword 列から発音ボタンの View を組む。

    - 単語の発音ボタンは英語学習者(lang="en")にだけ出す。
      日本語は漢字読みが「発音」と一対一でないため、単語単位の音声化は提供しない
      (例文単位の音声は別ルートで扱う)。
    - headwords が空 or lang != "en" → None (呼び出し側で view を付けない)
    - Discord の 1 ActionRow は最大 5 ボタンなので、超過分は捨てる
    - timeout=None: bot 再起動後も custom_id 経由で復元できる(状態を持たない設計)
    """
    if not headwords or lang != "en":
        return None

    view = discord.ui.View(timeout=None)
    for headword in headwords[:_MAX_BUTTONS_PER_ROW]:
        button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=headword,
            emoji="🔊",
            custom_id=_build_custom_id(lang, headword),
        )
        view.add_item(button)
    return view


async def handle_audio_click(
    interaction: discord.Interaction,
    lang: str,
    headword: str,
) -> None:
    """発音ボタンクリック: TTS を合成して ephemeral で本人にだけ返す。"""
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        audio = await asyncio.to_thread(tts.synthesize_word, headword, lang)
    except Exception:
        logger.exception(
            "TTS synthesis failed (lang=%s, headword=%r)", lang, headword
        )
        await interaction.followup.send(
            "音声生成に失敗しました。少し後でもう一度押してみて。",
            ephemeral=True,
        )
        return

    filename = f"{_safe_filename_stem(headword)}.mp3"
    await interaction.followup.send(
        file=discord.File(io.BytesIO(audio), filename=filename),
        ephemeral=True,
    )
