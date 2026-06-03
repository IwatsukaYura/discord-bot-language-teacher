import asyncio
import io
import logging
import re
from typing import Final

import discord

from lib import tts

logger = logging.getLogger(__name__)

_CUSTOM_ID_PREFIX: Final[str] = "tts"
_EXAMPLE_CUSTOM_ID_PREFIX: Final[str] = "tts_ex"
_SUPPORTED_LANGS: Final[frozenset[str]] = frozenset({"en", "ja"})
_MAX_BUTTONS_PER_ROW: Final[int] = 5  # Discord ActionRow 上限
_FILENAME_UNSAFE: Final[re.Pattern[str]] = re.compile(r"\W+", re.UNICODE)
_EXAMPLE_FILENAME: Final[str] = "example.mp3"

# build_word_embed の _format_sense_body が組む例文行のフォーマット:
#   "{j}. {source}\n    → {translation}"
# このパターンで source 部分だけを抜き出す (j は 1-indexed、4 スペース + → が translation 行)。
_EXAMPLE_SOURCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\d+\.\s(.+?)\n\s{4}→\s", re.MULTILINE | re.DOTALL
)


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


def _build_example_custom_id(lang: str, sense_idx: int, example_idx: int) -> str:
    return f"{_EXAMPLE_CUSTOM_ID_PREFIX}:{lang}:{sense_idx}:{example_idx}"


def parse_word_example_custom_id(custom_id: str) -> tuple[str, int, int] | None:
    """custom_id が 'tts_ex:<lang>:<sense_idx>:<example_idx>' なら parse して返す。

    例文テキストそのものは Discord custom_id 100B 上限に収まらないので持たず、
    sense/example の index だけ保持する設計。クリック時に message.embeds から復元する
    (extract_word_example_text_from_embed)。
    """
    parts = custom_id.split(":")
    if len(parts) != 4 or parts[0] != _EXAMPLE_CUSTOM_ID_PREFIX:
        return None
    _, lang, sense_idx_s, example_idx_s = parts
    if lang not in _SUPPORTED_LANGS:
        return None
    try:
        sense_idx = int(sense_idx_s)
        example_idx = int(example_idx_s)
    except ValueError:
        return None
    if sense_idx < 0 or example_idx < 0:
        return None
    return lang, sense_idx, example_idx


def _example_button_label(sense_idx: int, example_idx: int, *, multi_sense: bool) -> str:
    """例文音声ボタンの表示ラベル。

    - 単一 sense: "例文1", "例文2", ... (sense 番号は冗長なので省略)
    - 複数 sense: "1-1", "1-2", "2-1", ... (sense 番号-例文番号、いずれも 1-indexed)
    """
    if multi_sense:
        return f"{sense_idx + 1}-{example_idx + 1}"
    return f"例文{example_idx + 1}"


def build_word_audio_view(
    headwords: list[str],
    senses: list[dict],
    lang: str,
) -> discord.ui.View | None:
    """word ハンドラ結果用の View を組む(発音ボタン + 例文音声ボタン)。

    - lang="en" のとき: 各 headword の発音ボタン (最大 5 個、ActionRow 上限) を先に追加。
      これは英単語の発音学習用。日本語学習者には発音ボタンは出さない (漢字読みの概念
      が異なるため)。
    - lang in {"en","ja"}: 各 sense の examples すべてに例文音声ボタンを追加。
      label は単一 sense なら "例文N"、複数 sense なら "S-E" 形式。
    - 何も追加するものがなければ (lang 未対応、senses 空、例文ゼロ) None。
    - timeout=None: bot 再起動後も custom_id 経由で復元可能。
    """
    if lang not in _SUPPORTED_LANGS:
        return None

    view = discord.ui.View(timeout=None)

    if lang == "en":
        for headword in headwords[:_MAX_BUTTONS_PER_ROW]:
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=headword,
                    emoji="🔊",
                    custom_id=_build_custom_id(lang, headword),
                )
            )

    multi_sense = len(senses) > 1
    for sense_idx, sense in enumerate(senses):
        for example_idx, _ in enumerate(sense.get("examples", [])):
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=_example_button_label(
                        sense_idx, example_idx, multi_sense=multi_sense
                    ),
                    emoji="🔊",
                    custom_id=_build_example_custom_id(lang, sense_idx, example_idx),
                )
            )

    return view if view.children else None


def extract_word_example_text_from_embed(
    embed: discord.Embed,
    sense_idx: int,
    example_idx: int,
) -> str | None:
    """word embed の field から sense_idx 番目の sense → example_idx 番目の例文を取り出す。

    build_word_embed が `_format_sense_body` で組む書式
    ("{j}. {source}\\n    → {translation}") を正規表現でパースする。
    最後の field は 🔗 (辞書リンク) なので、その手前までを sense とみなす。
    """
    # 辞書リンク field (name="🔗") を除いた sense field 群を対象にする。
    # build_word_embed では最後に辞書リンク field が付くが、name で判定すれば
    # 位置に依存しない (将来 embed 構成が変わってもズレない)。
    sense_fields = [
        f for f in embed.fields
        if not (f.name and f.name.strip() == "🔗")
    ]
    if sense_idx < 0 or sense_idx >= len(sense_fields):
        return None
    value = sense_fields[sense_idx].value or ""
    matches = _EXAMPLE_SOURCE_PATTERN.findall(value)
    if example_idx < 0 or example_idx >= len(matches):
        return None
    return matches[example_idx]


async def handle_word_example_audio_click(
    interaction: discord.Interaction,
    lang: str,
    sense_idx: int,
    example_idx: int,
) -> None:
    """例文音声ボタンクリック: message.embeds から例文を復元して TTS 再生。"""
    await interaction.response.defer(ephemeral=True, thinking=True)

    message = interaction.message
    source_text = None
    if message is not None and message.embeds:
        source_text = extract_word_example_text_from_embed(
            message.embeds[0], sense_idx, example_idx
        )

    if source_text is None:
        logger.warning(
            "Could not extract example text (lang=%s, sense=%d, example=%d)",
            lang, sense_idx, example_idx,
        )
        await interaction.followup.send(
            "例文を読み取れませんでした。", ephemeral=True
        )
        return

    try:
        audio = await asyncio.to_thread(tts.synthesize_word, source_text, lang)
    except Exception:
        logger.exception(
            "TTS synthesis failed for example (lang=%s, sense=%d, example=%d, text_len=%d)",
            lang, sense_idx, example_idx, len(source_text),
        )
        await interaction.followup.send(
            "音声生成に失敗しました。少し後でもう一度押してみて。",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        file=discord.File(io.BytesIO(audio), filename=_EXAMPLE_FILENAME),
        ephemeral=True,
    )
