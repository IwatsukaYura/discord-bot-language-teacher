import asyncio
import io
import logging
import re
from typing import Final

import discord

from lib import embeds, tts

logger = logging.getLogger(__name__)

_CUSTOM_ID_PREFIX: Final[str] = "tts"
_SENTENCE_CUSTOM_ID_PREFIX: Final[str] = "tts_sentence"
_SUPPORTED_LANGS: Final[frozenset[str]] = frozenset({"en", "ja"})
_MAX_BUTTONS_PER_ROW: Final[int] = 5  # Discord ActionRow 上限
_FILENAME_UNSAFE: Final[re.Pattern[str]] = re.compile(r"\W+", re.UNICODE)
_SENTENCE_FILENAME: Final[str] = "sentence.mp3"


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


def _build_sentence_custom_id(lang: str) -> str:
    return f"{_SENTENCE_CUSTOM_ID_PREFIX}:{lang}"


def parse_sentence_custom_id(custom_id: str) -> str | None:
    """custom_id が 'tts_sentence:<lang>' なら lang を返す。

    例文テキストそのものは Discord の custom_id 100B 上限に収まらないので持たない。
    クリック時に message.embeds から復元する設計 (extract_sentence_text_from_embed)。
    """
    parts = custom_id.split(":", 1)
    if len(parts) != 2 or parts[0] != _SENTENCE_CUSTOM_ID_PREFIX:
        return None
    lang = parts[1]
    if lang not in _SUPPORTED_LANGS:
        return None
    return lang


def build_sentence_audio_view(lang: str) -> discord.ui.View | None:
    """例文音声ボタンの View を組む (ボタン1つ)。

    例文音声は en/ja どちらの学習者にも提供する。
    日本語学習者にとっては例文中の漢字読みを耳で確認できる手段になる。
    """
    if lang not in _SUPPORTED_LANGS:
        return None

    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="例文を聞く" if lang == "ja" else "Listen",
            emoji="🔊",
            custom_id=_build_sentence_custom_id(lang),
        )
    )
    return view


def extract_sentence_text_from_embed(embed: discord.Embed) -> str | None:
    """sentence の embed.title から source_text を取り出す。

    build_sentence_embed が `📝 {source_text}` の形で title を組むので、
    プレフィックスを剥がして本文だけを返す。プレフィックスが無い (= 例文embedでない)
    場合や、剥がした結果が空 (空白のみ含む) の場合は None。
    """
    title = embed.title
    if not title or not title.startswith(embeds.SENTENCE_TITLE_PREFIX):
        return None
    text = title[len(embeds.SENTENCE_TITLE_PREFIX):]
    return text if text.strip() else None


async def handle_sentence_audio_click(
    interaction: discord.Interaction,
    lang: str,
) -> None:
    """例文音声ボタンクリック: message.embeds から source_text を復元して TTS 再生。"""
    await interaction.response.defer(ephemeral=True, thinking=True)

    message = interaction.message
    source_text = None
    if message is not None and message.embeds:
        source_text = extract_sentence_text_from_embed(message.embeds[0])

    if source_text is None:
        logger.warning(
            "Could not extract sentence text from message embeds (lang=%s)", lang
        )
        await interaction.followup.send(
            "例文を読み取れませんでした。", ephemeral=True
        )
        return

    try:
        audio = await asyncio.to_thread(tts.synthesize_word, source_text, lang)
    except Exception:
        logger.exception(
            "TTS synthesis failed for sentence (lang=%s, text_len=%d)",
            lang, len(source_text),
        )
        await interaction.followup.send(
            "音声生成に失敗しました。少し後でもう一度押してみて。",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        file=discord.File(io.BytesIO(audio), filename=_SENTENCE_FILENAME),
        ephemeral=True,
    )
