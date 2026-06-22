import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import discord

from audio import playback
from config import BotConfig
from db import query_log
from handlers import grammar_handler, router, sentence_handler, word_handler
from lib.embeds import build_grammar_embed, build_sentence_embed, build_word_embed
from lib.script import matches_target_lang

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


def _extract_unique_translations(senses: list[dict]) -> list[str]:
    """全 senses の translations を平坦化し初出順を保ったまま重複除去。"""
    seen: list[str] = []
    for sense in senses:
        for t in sense.get("translations", []):
            if t and t not in seen:
                seen.append(t)
    return seen


def _summarize_word_result(query_text: str, senses: list[dict], target_lang: str) -> str:
    """result_summary 用: MODE A は translations、MODE B は headwords を ' / ' で連結。

    MODE A (query_text が target_lang のスクリプト) では headword が入力と同一なので
    意味側 (explanation_lang) の translations を保存しないと週次レポート/Anki カードが
    "complacent — complacent" のような無意味表示になる。判定は anki_card と同じ
    matches_target_lang を使う。
    """
    if matches_target_lang(query_text, target_lang):
        return " / ".join(_extract_unique_translations(senses))
    return _summarize_headwords(senses)


# (query_text, result_summary, reading) — query_log 保存用フィールドの組
LogFields = tuple[str, str, str]


@dataclass(frozen=True)
class QueryRoute:
    """入力種別 1 つ分の (ハンドラ, ログ項目抽出, 表示組み立て) の組。

    新しい入力種別を増やすときは _QUERY_ROUTES にルートを 1 件追加する。
    """

    kind: str
    handle: Callable[[str, BotConfig], Awaitable[dict]]
    log_fields: Callable[[str, dict, str], LogFields]
    render: Callable[[dict, BotConfig], tuple[discord.Embed, discord.ui.View | None]]


async def _handle_word_query(user_text: str, bot_config: BotConfig) -> dict:
    return await word_handler.handle_word(
        word=user_text,
        target_lang=bot_config.target_lang,
        explanation_lang=bot_config.explanation_lang,
        dictionary_url_template=bot_config.dictionary_url_template,
    )


def _word_log_fields(user_text: str, result: dict, target_lang: str) -> LogFields:
    summary = _summarize_word_result(result["input"], result["senses"], target_lang)
    return result["input"], summary, ""


def _render_word(
    result: dict, bot_config: BotConfig,
) -> tuple[discord.Embed, discord.ui.View | None]:
    embed = build_word_embed(result, bot_config.target_lang, bot_config.explanation_lang)
    view = playback.build_word_audio_view(
        headwords=_extract_unique_headwords(result["senses"]),
        senses=result["senses"],
        lang=bot_config.target_lang,
    )
    return embed, view


async def _handle_sentence_query(user_text: str, bot_config: BotConfig) -> dict:
    return await sentence_handler.handle_sentence(
        text=user_text,
        target_lang=bot_config.target_lang,
        explanation_lang=bot_config.explanation_lang,
    )


def _sentence_log_fields(user_text: str, result: dict, target_lang: str) -> LogFields:
    return result["source_text"], result["translation"], result.get("source_reading", "")


def _render_sentence(
    result: dict, bot_config: BotConfig,
) -> tuple[discord.Embed, discord.ui.View | None]:
    return build_sentence_embed(result, bot_config.target_lang, bot_config.explanation_lang), None


async def _handle_grammar_query(user_text: str, bot_config: BotConfig) -> dict:
    return await grammar_handler.handle_grammar(
        user_text,
        target_lang=bot_config.target_lang,
        explanation_lang=bot_config.explanation_lang,
    )


def _grammar_log_fields(user_text: str, result: dict, target_lang: str) -> LogFields:
    return user_text, result["topic"], ""


def _render_grammar(
    result: dict, bot_config: BotConfig,
) -> tuple[discord.Embed, discord.ui.View | None]:
    return build_grammar_embed(result), None


_QUERY_ROUTES: dict[str, QueryRoute] = {
    "word": QueryRoute("word", _handle_word_query, _word_log_fields, _render_word),
    "sentence": QueryRoute(
        "sentence", _handle_sentence_query, _sentence_log_fields, _render_sentence,
    ),
    "grammar": QueryRoute(
        "grammar", _handle_grammar_query, _grammar_log_fields, _render_grammar,
    ),
}


def _log_query(
    route: QueryRoute,
    user_text: str,
    result: dict,
    user_id: str,
    user_name: str,
    bot_config: BotConfig,
) -> None:
    """query_log への保存。失敗しても応答は返したいので warning に留める。"""
    try:
        query_text, result_summary, reading = route.log_fields(
            user_text, result, bot_config.target_lang,
        )
        query_log.insert_query_log(
            kind=route.kind,
            target_lang=bot_config.target_lang,
            discord_user_id=user_id,
            discord_user_name=user_name,
            query_text=query_text,
            result_summary=result_summary,
            reading=reading,
        )
    except Exception as e:
        logger.warning("Failed to log %s query: %s", route.kind, e)


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

    # router は word/sentence/grammar のみ返すが、未知種別は従来どおり grammar 扱い。
    route = _QUERY_ROUTES.get(input_type, _QUERY_ROUTES["grammar"])

    t_gen = time.perf_counter()
    try:
        result = await route.handle(user_text, bot_config)
        _log_query(route, user_text, result, user_id, user_name, bot_config)
        return route.render(result, bot_config)
    finally:
        generate_sec = time.perf_counter() - t_gen
        logger.info(
            "dispatch timing: type=%s classify=%.2fs generate=%.2fs total=%.2fs",
            input_type, classify_sec, generate_sec, classify_sec + generate_sec,
        )
