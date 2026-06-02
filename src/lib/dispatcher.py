import asyncio
import io
import logging
import re
import time

import discord

from config import BotConfig
from db import query_log
from handlers import grammar_handler, router, sentence_handler, word_handler
from lib import tts
from lib.embeds import build_grammar_embed, build_sentence_embed, build_word_embed

logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"<@!?\d+>")
_FILENAME_UNSAFE = re.compile(r"\W+", re.UNICODE)


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


def _safe_filename_stem(headword: str) -> str:
    """Discord 添付ファイル名向けに headword をサニタイズ。

    日本語などの Unicode 単語文字は保持し、句読点/記号は '_' に置換。
    全て除去された場合は 'audio' にフォールバック。
    """
    base = _FILENAME_UNSAFE.sub("_", headword).strip("_")
    return base if base else "audio"


async def _build_word_audio_files(
    senses: list[dict],
    target_lang: str,
) -> list[discord.File]:
    """ユニーク headword ごとに発音 mp3 を生成し discord.File のリストを返す。

    個別 TTS 失敗はログ警告のみで該当 headword をスキップし、他は続行する。
    """
    headwords = _extract_unique_headwords(senses)
    if not headwords:
        return []

    tasks = [
        asyncio.to_thread(tts.synthesize_word, headword, target_lang)
        for headword in headwords
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    files: list[discord.File] = []
    for headword, result in zip(headwords, results):
        if isinstance(result, BaseException):
            logger.warning(
                "TTS failed for %r (lang=%s): %s", headword, target_lang, result
            )
            continue
        stem = _safe_filename_stem(headword)
        files.append(discord.File(io.BytesIO(result), filename=f"{stem}.mp3"))
    return files


async def dispatch(
    user_text: str,
    user_id: str,
    user_name: str,
    bot_config: BotConfig,
) -> tuple[discord.Embed, list[discord.File]]:
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
            audio_files = await _build_word_audio_files(result["senses"], target_lang)
            return embed, audio_files

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
            return build_sentence_embed(result, target_lang, explanation_lang), []

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
        return build_grammar_embed(result), []
    finally:
        generate_sec = time.perf_counter() - t_gen
        logger.info(
            "dispatch timing: type=%s classify=%.2fs generate=%.2fs total=%.2fs",
            input_type, classify_sec, generate_sec, classify_sec + generate_sec,
        )
