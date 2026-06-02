import discord

_EMBED_FIELD_MAX = 1024
_EMBED_TITLE_MAX = 200

# build_sentence_embed が組み立てる title の絵文字プレフィックス。
# 例: "📝 I went to the park yesterday."
# playback 側でクリック時に title から source_text を復元するため、ここを唯一の出典とする。
SENTENCE_TITLE_PREFIX = "📝 "


def _truncate(text: str, max_len: int = _EMBED_FIELD_MAX) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _color_for(target_lang: str) -> discord.Color:
    return discord.Color.blue() if target_lang == "en" else discord.Color.red()


def _set_model_footer(embed: discord.Embed, result: dict) -> None:
    model_label = result.get("model_label")
    if model_label:
        embed.set_footer(text=f"via {model_label}")


def _format_sense_heading(sense: dict, index: int, multi: bool) -> str:
    headword = sense["headword"]
    reading = sense.get("headword_reading", "")
    pos = sense.get("part_of_speech", "")
    reading_part = f"【{reading}】" if reading else ""
    pos_part = f" ({pos})" if pos else ""
    prefix = f"【{index}】 " if multi else ""
    return f"{prefix}{headword}{reading_part}{pos_part}"


def _format_sense_body(sense: dict, is_ja: bool) -> str:
    translation_label = "訳" if is_ja else "Translation"

    lines = []
    translations = sense.get("translations", [])
    if translations:
        lines.append(f"**{translation_label}**: {' / '.join(translations)}")

    examples = sense.get("examples", [])
    if examples:
        if lines:
            lines.append("")
        for j, e in enumerate(examples, start=1):
            lines.append(f"{j}. {e['source']}")
            lines.append(f"    → {e['translation']}")
    return "\n".join(lines)


def build_word_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
    title = f"📘 {result['input']}"
    embed = discord.Embed(title=_truncate(title, _EMBED_TITLE_MAX), color=_color_for(target_lang))

    is_ja = explanation_lang == "ja"
    senses = result["senses"]
    multi = len(senses) > 1

    for i, sense in enumerate(senses, start=1):
        embed.add_field(
            name=_truncate(_format_sense_heading(sense, i, multi), _EMBED_TITLE_MAX),
            value=_truncate(_format_sense_body(sense, is_ja)),
            inline=False,
        )

    label_link = "辞書で見る" if is_ja else "View in dictionary"
    embed.add_field(name="🔗", value=f"[{label_link}]({result['dictionary_url']})", inline=False)
    _set_model_footer(embed, result)
    return embed


def build_sentence_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
    source_reading = result.get("source_reading", "")
    title = f"{SENTENCE_TITLE_PREFIX}{_truncate(result['source_text'], _EMBED_TITLE_MAX)}"
    embed = discord.Embed(title=title, color=_color_for(target_lang))

    if source_reading:
        embed.description = f"【{source_reading}】"

    is_ja = explanation_lang == "ja"
    embed.add_field(name="訳" if is_ja else "Translation", value=_truncate(result["translation"]), inline=False)

    if result["literal_translation"]:
        embed.add_field(
            name="直訳" if is_ja else "Literal",
            value=_truncate(result["literal_translation"]),
            inline=False,
        )

    if result["key_points"]:
        points_text = "\n".join(f"• {p}" for p in result["key_points"])
        embed.add_field(
            name="ポイント" if is_ja else "Key Points",
            value=_truncate(points_text),
            inline=False,
        )

    _set_model_footer(embed, result)
    return embed


def build_grammar_embed(result: dict) -> discord.Embed:
    target_lang = result["target_lang"]
    explanation_lang = result["explanation_lang"]
    title = f"📚 {_truncate(result['topic'], _EMBED_TITLE_MAX)}"
    embed = discord.Embed(title=title, color=_color_for(target_lang))

    is_ja = explanation_lang == "ja"
    embed.add_field(
        name="解説" if is_ja else "Explanation",
        value=_truncate(result["explanation"]),
        inline=False,
    )

    if result["examples"]:
        examples_text = "\n\n".join(
            f"{i+1}. {e['source']}\n    → {e['translation']}"
            for i, e in enumerate(result["examples"])
        )
        embed.add_field(
            name="例文" if is_ja else "Examples",
            value=_truncate(examples_text),
            inline=False,
        )

    if result["related"]:
        embed.add_field(
            name="関連" if is_ja else "Related",
            value=_truncate(result["related"]),
            inline=False,
        )

    _set_model_footer(embed, result)
    return embed
