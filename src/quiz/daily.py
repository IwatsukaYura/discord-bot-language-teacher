import logging
import random
from pathlib import Path

import discord

from db import quiz_log
from handlers import quiz_handler
from quiz import poster

logger = logging.getLogger(__name__)


def _explanation_lang_for(target_lang: str) -> str:
    return "ja" if target_lang == "en" else "en"


async def post_daily_quizzes_for_learner(
    client: discord.Client,
    channel_id: int,
    learner: dict,
    db_path: Path | None = None,
) -> None:
    """指定 learner に対して日次クイズを投稿。learner は {discord_user_id, name, target_lang}。"""
    if db_path is None:
        db_path = quiz_log.DEFAULT_DB_PATH

    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)

    try:
        await _post_for_learner(channel, learner, db_path)
    except Exception:
        logger.exception("Failed to post daily quiz for learner %s", learner.get("name"))


async def _post_for_learner(
    channel: discord.abc.Messageable,
    learner: dict,
    db_path: Path,
) -> None:
    user_id = learner["discord_user_id"]
    target_lang = learner["target_lang"]

    word_history = quiz_log.get_user_word_history(user_id, target_lang, db_path=db_path)

    if not word_history:
        logger.info("Learner %s has no word history; posting new-only quiz", learner.get("name"))
        await _post_one(channel, learner, mode="new", review_source=None,
                        db_path=db_path, position=(1, 1))
        return

    recent_quiz_sources = quiz_log.get_recent_quiz_source_texts(
        user_id, target_lang, days=14, db_path=db_path,
    )
    review_candidates = [w for w in word_history if w not in recent_quiz_sources]

    if not review_candidates:
        logger.info("All recent words for %s are within 14-day cooldown; new-only quiz",
                    learner.get("name"))
        await _post_one(channel, learner, mode="new", review_source=None,
                        db_path=db_path, position=(1, 1))
        return

    review_source = random.choice(review_candidates)
    await _post_one(channel, learner, mode="review", review_source=review_source,
                    db_path=db_path, position=(1, 2))
    await _post_one(channel, learner, mode="new", review_source=None,
                    db_path=db_path, position=(2, 2))


async def _post_one(
    channel: discord.abc.Messageable,
    learner: dict,
    mode: str,
    review_source: str | None,
    db_path: Path,
    position: tuple[int, int],
) -> None:
    user_id = learner["discord_user_id"]
    target_lang = learner["target_lang"]
    explanation_lang = _explanation_lang_for(target_lang)

    if mode == "review":
        if review_source is None:
            raise ValueError("review mode requires review_source")
        quiz_content = await quiz_handler.generate_review_quiz(
            source_word=review_source,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
        )
        source_text = review_source
    else:
        recent = quiz_log.get_recent_query_history(user_id, target_lang, limit=30, db_path=db_path)
        all_past_quiz = quiz_log.get_all_quiz_source_texts(user_id, target_lang, db_path=db_path)
        all_words = quiz_log.get_user_word_history(user_id, target_lang, db_path=db_path)
        exclusion = list(set(all_past_quiz + all_words))
        quiz_content = await quiz_handler.generate_new_quiz(
            history=recent,
            exclusion_list=exclusion,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
        )
        source_text = quiz_content["source_text"]

    quiz_id = quiz_log.insert_quiz(
        discord_user_id=user_id,
        target_lang=target_lang,
        kind="word",
        mode=mode,
        source_text=source_text,
        question_text=quiz_content["question_text"],
        choices=quiz_content["choices"],
        correct_index=quiz_content["correct_index"],
        explanation=quiz_content["explanation"],
        db_path=db_path,
    )

    embed = poster.build_quiz_embed(
        source_text=source_text,
        question_text=quiz_content["question_text"],
        target_lang=target_lang,
        explanation_lang=explanation_lang,
        mode=mode,
        position=position,
    )
    view = poster.QuizView(quiz_id=quiz_id, choices=quiz_content["choices"])

    mention = f"<@{user_id}>"
    msg = await channel.send(content=mention, embed=embed, view=view)
    quiz_log.set_message_id(quiz_id, str(msg.id), db_path=db_path)

    logger.info("Posted %s quiz to %s (quiz_id=%d, source=%s)",
                mode, learner.get("name"), quiz_id, source_text)


async def handle_quiz_answer(
    interaction: discord.Interaction,
    quiz_id: int,
    choice_index: int,
    db_path: Path | None = None,
) -> None:
    """ボタン押下をハンドル: 本人検証 → 採点 → 即時返答。"""
    if db_path is None:
        db_path = quiz_log.DEFAULT_DB_PATH

    quiz = quiz_log.get_quiz_by_id(quiz_id, db_path=db_path)
    if quiz is None:
        await interaction.response.send_message("クイズが見つからないみたい。", ephemeral=True)
        return

    explanation_lang = _explanation_lang_for(quiz["target_lang"])
    is_ja = explanation_lang == "ja"

    if str(interaction.user.id) != quiz["discord_user_id"]:
        msg = "これはあなたのクイズじゃないよ。" if is_ja else "This isn't your quiz."
        await interaction.response.send_message(msg, ephemeral=True)
        return

    if quiz["answered_at"] is not None:
        msg = "もう回答済みだよ。" if is_ja else "You've already answered."
        await interaction.response.send_message(msg, ephemeral=True)
        return

    is_correct = (choice_index == quiz["correct_index"])
    quiz_log.record_answer(quiz_id, choice_index, is_correct, db_path=db_path)

    correct_choice = quiz["choices"][quiz["correct_index"]]
    chosen = quiz["choices"][choice_index]

    if is_correct:
        header = "✅ 正解!" if is_ja else "✅ Correct!"
        body_lines = [
            f"**{quiz['source_text']}** = {correct_choice}",
            "",
            quiz["explanation"],
        ]
    else:
        header = "❌ 不正解" if is_ja else "❌ Not quite"
        line_chosen = f"選んだ答え: {chosen}" if is_ja else f"Your answer: {chosen}"
        line_correct = (
            f"正解: **{quiz['source_text']}** = {correct_choice}"
            if is_ja
            else f"Correct: **{quiz['source_text']}** = {correct_choice}"
        )
        body_lines = [line_chosen, line_correct, "", quiz["explanation"]]

    await interaction.response.send_message(f"{header}\n" + "\n".join(body_lines))
