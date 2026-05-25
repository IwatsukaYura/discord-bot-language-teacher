import os
import logging
import re

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from db import query_log
from handlers import grammar_handler, router, sentence_handler, word_handler
from reports import weekly

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
_scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")

_JAPANESE_PATTERN = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]")
_MENTION_PATTERN = re.compile(r"<@!?\d+>")
_CAMBRIDGE_URL = "https://dictionary.cambridge.org/dictionary/english/{word}"
_JISHO_URL = "https://jisho.org/search/{word}"
_EMBED_FIELD_MAX = 1024
_EMBED_TITLE_MAX = 200
_GRIZZO_COMMENT_MAX = 300


def _contains_japanese(text: str) -> bool:
    return bool(_JAPANESE_PATTERN.search(text))


def _extract_user_text(content: str) -> str:
    return _MENTION_PATTERN.sub("", content).strip()


def _truncate(text: str, max_len: int = _EMBED_FIELD_MAX) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _color_for(target_lang: str) -> discord.Color:
    return discord.Color.blue() if target_lang == "en" else discord.Color.red()


def _build_word_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
    reading = result.get("reading", "")
    reading_part = f"【{reading}】" if reading else ""
    title = f"📘 {result['word']}{reading_part} ({result['part_of_speech']})"
    embed = discord.Embed(title=_truncate(title, _EMBED_TITLE_MAX), color=_color_for(target_lang))

    comment = result.get("grizzo_comment", "").strip()
    if comment:
        embed.description = _truncate(comment, _GRIZZO_COMMENT_MAX)

    is_ja = explanation_lang == "ja"
    embed.add_field(name="訳" if is_ja else "Translation", value=_truncate(result["translation"]), inline=False)
    embed.add_field(name="意味" if is_ja else "Meaning", value=_truncate(result["meaning"]), inline=False)
    embed.add_field(name="使い方" if is_ja else "Usage", value=_truncate(result["usage"]), inline=False)

    examples_text = "\n\n".join(
        f"{i+1}. {e['source']}\n    → {e['translation']}"
        for i, e in enumerate(result["examples"])
    )
    if examples_text:
        embed.add_field(name="例文" if is_ja else "Examples", value=_truncate(examples_text), inline=False)

    label_link = "辞書で見る" if is_ja else "View in dictionary"
    embed.add_field(name="🔗", value=f"[{label_link}]({result['dictionary_url']})", inline=False)
    return embed


def _build_sentence_embed(result: dict, target_lang: str, explanation_lang: str) -> discord.Embed:
    title = f"📝 {_truncate(result['source_text'], _EMBED_TITLE_MAX)}"
    embed = discord.Embed(title=title, color=_color_for(target_lang))

    comment = result.get("grizzo_comment", "").strip()
    if comment:
        embed.description = _truncate(comment, _GRIZZO_COMMENT_MAX)

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

    comment = result.get("grizzo_comment", "").strip()
    if comment:
        embed.description = _truncate(comment, _GRIZZO_COMMENT_MAX)

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

    if input_type == "word":
        is_japanese = _contains_japanese(user_text)
        target_lang = "ja" if is_japanese else "en"
        explanation_lang = "en" if is_japanese else "ja"
        url_template = _JISHO_URL if is_japanese else _CAMBRIDGE_URL
        result = await word_handler.handle_word(
            word=user_text,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
            dictionary_url_template=url_template,
        )
        try:
            query_log.insert_query_log(
                kind="word",
                target_lang=target_lang,
                discord_user_id=user_id,
                discord_user_name=user_name,
                query_text=user_text,
                result_summary=result["translation"],
                reading=result.get("reading", ""),
            )
        except Exception as e:
            logger.warning("Failed to log word query: %s", e)
        return _build_word_embed(result, target_lang, explanation_lang)

    if input_type == "sentence":
        is_japanese = _contains_japanese(user_text)
        target_lang = "ja" if is_japanese else "en"
        explanation_lang = "en" if is_japanese else "ja"
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
                query_text=user_text,
                result_summary=result["translation"],
            )
        except Exception as e:
            logger.warning("Failed to log sentence query: %s", e)
        return _build_sentence_embed(result, target_lang, explanation_lang)

    result = await grammar_handler.handle_grammar(user_text)
    try:
        query_log.insert_query_log(
            kind="grammar",
            target_lang=result["target_lang"],
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
    logger.info(f"Logged in as {client.user} (id={client.user.id})")
    _setup_weekly_scheduler()


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
        args=[client, channel_id],
        id="weekly_report",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Weekly report scheduler started (Sunday 21:00 JST)")


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
    client.run(token)


if __name__ == "__main__":
    main()
