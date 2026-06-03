import logging
import re
import time

import discord

from audio import playback
from config import BotConfig
from db import query_log
from handlers import grammar_handler, router, sentence_handler, word_handler
from lib.embeds import build_grammar_embed, build_sentence_embed, build_word_embed

logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"<@!?\d+>")


def extract_user_text(content: str) -> str:
    return _MENTION_PATTERN.sub("", content).strip()


def _extract_unique_headwords(senses: list[dict]) -> list[str]:
    """senses から初出順を保ったまま重複を除いた headword 列を返す。"""
    seen: list[str] = []
    for sense in senses:
        h = sense["headword"]
        if h not in seen:
            seen.append(h)
    return seen


def _summarize_headwords(senses: list[dict]) -> str:
    """query_log.result_summary 用: ユニーク headword を ' / ' 区切りで連結。"""
    return " / ".join(_extract_unique_headwords(senses))


async def dispatch(
    user_text: str,
    user_id: str,
    user_name: str,
    bot_config: BotConfig,
) -> tuple[discord.Embed, discord.ui.View | None]:
    t_start = time.perf_counter()
    input_type = await router.classify_input(user_text)
    classify_sec = time.perf_counter() - t_start
    logger.info("Classified %r as %s", user_text, input_type)

    target_lang = bot_config.target_lang
    explanation_lang = bot_config.explanation_lang

    t_gen = time.perf_counter()
    try:
        if input_type == "word":
            result = await word_handler.handle_word(
                word=user_text,
                target_lang=target_lang,
                explanation_lang=explanation_lang,
                dictionary_url_template=bot_config.dictionary_url_template,
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
            embed = build_word_embed(result, target_lang, explanation_lang)
            headwords = _extract_unique_headwords(result["senses"])
            view = playback.build_word_audio_view(
                headwords=headwords,
                senses=result["senses"],
                lang=target_lang,
            )
            return embed, view

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
            return build_sentence_embed(result, target_lang, explanation_lang), None

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
        return build_grammar_embed(result), None
    finally:
        generate_sec = time.perf_counter() - t_gen
        logger.info(
            "dispatch timing: type=%s classify=%.2fs generate=%.2fs total=%.2fs",
            input_type, classify_sec, generate_sec, classify_sec + generate_sec,
        )
