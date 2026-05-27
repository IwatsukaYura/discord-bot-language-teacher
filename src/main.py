import os
import logging
import re

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from config import BotConfig, load_bot_config
from db import query_log, quiz_log
from handlers import grammar_handler, router, sentence_handler, word_handler
from quiz import daily as quiz_daily
from quiz import poster as quiz_poster
from reports import weekly

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_bot_config: BotConfig = load_bot_config()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
_scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")

_MENTION_PATTERN = re.compile(r"<@!?\d+>")
_EMBED_FIELD_MAX = 1024
_EMBED_TITLE_MAX = 200


def _extract_user_text(content: str) -> str:
    return _MENTION_PATTERN.sub("", content).strip()


def _truncate(text: str, max_len: int = _EMBED_FIELD_MAX) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _color_for(target_lang: str) -> discord.Color:
    return discord.Color.blue() if target_lang == "en" else discord.Color.red()


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
    meaning_label = "意味" if is_ja else "Meaning"
    usage_label = "使い方" if is_ja else "Usage"

    lines = []
    translations = sense.get("translations", [])
    if translations:
        lines.append(f"**{translation_label}**: {' / '.join(translations)}")
    lines.append(f"**{meaning_label}**: {sense['meaning']}")
    lines.append(f"**{usage_label}**: {sense['usage']}")

    examples = sense.get("examples", [])
    if examples:
        lines.append("")
        for j, e in enumerate(examples, start=1):
            lines.append(f"{j}. {e['source']}")
            lines.append(f"    → {e['translation']}")
    return "\n".join(lines)


def _build_word_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
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
    return embed


def _summarize_headwords(senses: list[dict]) -> str:
    """query_log.result_summary 用: 全 sense の headword を ' / ' 区切りで連結(重複排除)。"""
    seen: list[str] = []
    for sense in senses:
        h = sense["headword"]
        if h not in seen:
            seen.append(h)
    return " / ".join(seen)


def _build_sentence_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
    source_reading = result.get("source_reading", "")
    reading_part = f"\n【{source_reading}】" if source_reading else ""
    title = f"📝 {_truncate(result['source_text'], _EMBED_TITLE_MAX)}"
    embed = discord.Embed(title=title, color=_color_for(target_lang))

    if reading_part:
        embed.description = reading_part.strip()

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

    return embed


def _build_grammar_embed(result: dict) -> discord.Embed:
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

    return embed


async def _dispatch(user_text: str, user_id: str, user_name: str) -> discord.Embed:
    input_type = await router.classify_input(user_text)
    logger.info("Classified %r as %s", user_text, input_type)

    target_lang = _bot_config.target_lang
    explanation_lang = _bot_config.explanation_lang

    if input_type == "word":
        result = await word_handler.handle_word(
            word=user_text,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
            dictionary_url_template=_bot_config.dictionary_url_template,
        )
        try:
            query_log.insert_query_log(
                kind="word",
                target_lang=target_lang,
                discord_user_id=user_id,
                discord_user_name=user_name,
                query_text=result["input"],
                result_summary=_summarize_headwords(result["senses"]),
                reading="",
            )
        except Exception as e:
            logger.warning("Failed to log word query: %s", e)
        return _build_word_embed(result, target_lang, explanation_lang)

    if input_type == "sentence":
        result = await sentence_handler.handle_sentence(
            text=user_text,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
        )
        try:
            query_log.insert_query_log(
                kind="sentence",
                target_lang=target_lang,
                discord_user_id=user_id,
                discord_user_name=user_name,
                query_text=result["source_text"],
                result_summary=result["translation"],
                reading=result.get("source_reading", ""),
            )
        except Exception as e:
            logger.warning("Failed to log sentence query: %s", e)
        return _build_sentence_embed(result, target_lang, explanation_lang)

    result = await grammar_handler.handle_grammar(
        user_text,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
    )
    try:
        query_log.insert_query_log(
            kind="grammar",
            target_lang=target_lang,
            discord_user_id=user_id,
            discord_user_name=user_name,
            query_text=user_text,
            result_summary=result["topic"],
        )
    except Exception as e:
        logger.warning("Failed to log grammar query: %s", e)
    return _build_grammar_embed(result)


@client.event
async def on_ready():
    logger.info(
        "Logged in as %s (id=%d, role=%s)",
        client.user, client.user.id, _bot_config.role,
    )
    _setup_weekly_scheduler()
    _setup_quiz_scheduler()


def _setup_weekly_scheduler() -> None:
    if _scheduler.running:
        return
    channel_id_str = os.getenv("REPORT_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("REPORT_CHANNEL_ID not set; weekly reports disabled")
        return
    channel_id = int(channel_id_str)
    _scheduler.add_job(
        weekly.post_weekly_reports,
        CronTrigger(day_of_week="sun", hour=21, minute=0, timezone="Asia/Tokyo"),
        args=[client, channel_id, _bot_config.target_lang, _bot_config.learner_name],
        id="weekly_report",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Weekly report scheduler started (Sunday 21:00 JST) for %s",
        _bot_config.learner_name,
    )


def _get_quiz_learner() -> dict | None:
    if not _bot_config.learner_discord_id:
        return None
    return {
        "discord_user_id": _bot_config.learner_discord_id,
        "name": _bot_config.learner_name,
        "target_lang": _bot_config.target_lang,
    }


def _setup_quiz_scheduler() -> None:
    channel_id_str = os.getenv("QUIZ_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("QUIZ_CHANNEL_ID not set; daily quiz disabled")
        return
    learner = _get_quiz_learner()
    if learner is None:
        logger.warning(
            "Learner Discord ID for BOT_ROLE=%s is not set; daily quiz disabled",
            _bot_config.role,
        )
        return
    channel_id = int(channel_id_str)
    _scheduler.add_job(
        quiz_daily.post_daily_quizzes_for_learner,
        CronTrigger(hour=8, minute=0, timezone="Asia/Tokyo"),
        args=[client, channel_id, learner],
        id="daily_quiz",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info("Daily quiz scheduler set (8:00 JST) for %s", learner["name"])


@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    if not interaction.data:
        return
    custom_id = interaction.data.get("custom_id", "")
    parsed = quiz_poster.parse_custom_id(custom_id)
    if parsed is None:
        return
    quiz_id, choice_index = parsed
    try:
        await quiz_daily.handle_quiz_answer(interaction, quiz_id, choice_index)
    except Exception:
        logger.exception("Failed to handle quiz answer (quiz_id=%d)", quiz_id)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "エラーが出たみたい。少し後でもう一度ボタンを押してみて。",
                ephemeral=True,
            )


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if client.user not in message.mentions:
        return

    user_text = _extract_user_text(message.content)
    if not user_text:
        await message.channel.send("単語または文章を一緒に書いてね (例: `@Bot apple`)")
        return

    async with message.channel.typing():
        try:
            embed = await _dispatch(
                user_text=user_text,
                user_id=str(message.author.id),
                user_name=message.author.display_name,
            )
            await message.channel.send(embed=embed)
        except Exception as e:
            logger.exception("Failed to handle query")
            await message.channel.send(f"ごめん、エラーが出ました: `{type(e).__name__}: {e}`")


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set in .env")
    query_log.init_db()
    quiz_log.init_db()
    client.run(token)


if __name__ == "__main__":
    main()
