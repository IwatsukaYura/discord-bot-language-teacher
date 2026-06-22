import logging
import random
from pathlib import Path

import discord

from db import quiz_log
from handlers import quiz_handler
from lib.lang import explanation_lang_for
from quiz import poster
from quiz.models import Learner, QuizContent

logger = logging.getLogger(__name__)


async def post_daily_quizzes_for_learner(
    client: discord.Client,
    channel_id: int,
    learner: Learner,
    db_path: Path | None = None,
) -> None:
    """指定 learner に対して日次クイズを投稿。"""
    if db_path is None:
        db_path = quiz_log.DEFAULT_DB_PATH

    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)

    try:
        await _post_for_learner(channel, learner, db_path)
    except Exception:
        logger.exception("Failed to post daily quiz for learner %s", learner.name)


async def _post_for_learner(
    channel: discord.abc.Messageable,
    learner: Learner,
    db_path: Path,
) -> None:
    user_id = learner.discord_user_id
    target_lang = learner.target_lang

    word_history = quiz_log.get_studied_target_lang_words(user_id, target_lang, db_path=db_path)

    if not word_history:
        logger.info("Learner %s has no word history; posting new-only quiz", learner.name)
        await _post_one(channel, learner, mode="new", review_source=None,
                        db_path=db_path, position=(1, 1))
        return

    recent_quiz_sources = quiz_log.get_recent_quiz_source_texts(
        user_id, target_lang, days=14, db_path=db_path,
    )
    review_candidates = [w for w in word_history if w not in recent_quiz_sources]

    if not review_candidates:
        logger.info("All recent words for %s are within 14-day cooldown; new-only quiz",
                    learner.name)
        await _post_one(channel, learner, mode="new", review_source=None,
                        db_path=db_path, position=(1, 1))
        return

    review_source = random.choice(review_candidates)
    await _post_one(channel, learner, mode="review", review_source=review_source,
                    db_path=db_path, position=(1, 2))
    await _post_one(channel, learner, mode="new", review_source=None,
                    db_path=db_path, position=(2, 2))


async def post_addon_quizzes(
    channel: discord.abc.Messageable,
    learner: Learner,
    count: int,
    db_path: Path | None = None,
) -> int:
    """ユーザー要求に応じて追加の新出クイズを count 問投稿し、実際に投稿できた数を返す。

    除外リストは 1 度だけ取得し、互いに異なる count 問をバッチ生成してから投稿する
    (1 問ずつ生成するより API コールを大幅に削減する)。
    呼び出し側は戻り値が 0 のとき「枠の返却」などの失敗ハンドリングに使う。
    """
    if db_path is None:
        db_path = quiz_log.DEFAULT_DB_PATH

    user_id = learner.discord_user_id
    target_lang = learner.target_lang
    explanation_lang = explanation_lang_for(target_lang)

    recent = quiz_log.get_recent_query_history(user_id, target_lang, limit=30, db_path=db_path)
    all_past_quiz = quiz_log.get_all_quiz_source_texts(user_id, target_lang, db_path=db_path)
    all_words = quiz_log.get_studied_target_lang_words(user_id, target_lang, db_path=db_path)
    exclusion = list(set(all_past_quiz + all_words))

    quizzes = await quiz_handler.generate_new_quiz_batch(
        count=count,
        history=recent,
        exclusion_list=exclusion,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
    )

    total = len(quizzes)
    posted = 0
    for i, quiz_content in enumerate(quizzes):
        try:
            await _send_quiz(
                channel, learner, mode="new",
                source_text=quiz_content.source_text,
                quiz_content=quiz_content,
                db_path=db_path, position=(i + 1, total), addon=True,
            )
            posted += 1
        except Exception:
            logger.exception("Failed to post addon quiz %d/%d for %s",
                             i + 1, total, learner.name)
    return posted


async def _post_one(
    channel: discord.abc.Messageable,
    learner: Learner,
    mode: str,
    review_source: str | None,
    db_path: Path,
    position: tuple[int, int],
    addon: bool = False,
) -> None:
    user_id = learner.discord_user_id
    target_lang = learner.target_lang
    explanation_lang = explanation_lang_for(target_lang)

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
        all_words = quiz_log.get_studied_target_lang_words(user_id, target_lang, db_path=db_path)
        exclusion = list(set(all_past_quiz + all_words))
        quiz_content = await quiz_handler.generate_new_quiz(
            history=recent,
            exclusion_list=exclusion,
            target_lang=target_lang,
            explanation_lang=explanation_lang,
        )
        source_text = quiz_content.source_text

    await _send_quiz(channel, learner, mode, source_text, quiz_content,
                     db_path=db_path, position=position, addon=addon)


async def _send_quiz(
    channel: discord.abc.Messageable,
    learner: Learner,
    mode: str,
    source_text: str,
    quiz_content: QuizContent,
    db_path: Path,
    position: tuple[int, int],
    addon: bool = False,
) -> None:
    """生成済みの quiz_content を DB 保存 → embed/ボタン付きで投稿する共通処理。"""
    user_id = learner.discord_user_id
    target_lang = learner.target_lang
    explanation_lang = explanation_lang_for(target_lang)

    quiz_id = quiz_log.insert_quiz(
        discord_user_id=user_id,
        target_lang=target_lang,
        kind="word",
        mode=mode,
        source_text=source_text,
        question_text=quiz_content.question_text,
        choices=quiz_content.choices,
        correct_index=quiz_content.correct_index,
        explanation=quiz_content.explanation,
        db_path=db_path,
    )

    embed = poster.build_quiz_embed(
        source_text=source_text,
        question_text=quiz_content.question_text,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
        mode=mode,
        position=position,
        addon=addon,
        model_label=quiz_content.model_label,
        reading=quiz_content.reading,
        example=quiz_content.example_sentence,
    )
    view = poster.QuizView(quiz_id=quiz_id, choices=quiz_content.choices)

    mention = f"<@{user_id}>"
    msg = await channel.send(content=mention, embed=embed, view=view)
    quiz_log.set_message_id(quiz_id, str(msg.id), db_path=db_path)

    logger.info("Posted %s quiz to %s (quiz_id=%d, source=%s)",
                mode, learner.name, quiz_id, source_text)


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

    explanation_lang = explanation_lang_for(quiz["target_lang"])
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

    await _maybe_offer_addon(
        interaction,
        user_id=quiz["discord_user_id"],
        target_lang=quiz["target_lang"],
        explanation_lang=explanation_lang,
        db_path=db_path,
    )


async def _maybe_offer_addon(
    interaction: discord.Interaction,
    user_id: str,
    target_lang: str,
    explanation_lang: str,
    db_path: Path,
) -> None:
    """今日のクイズを全て回答し終え、かつ追加枠が未使用なら追加プロンプトを出す。"""
    if quiz_log.count_unanswered_today(user_id, target_lang, db_path=db_path) > 0:
        return
    if quiz_log.has_used_addon_today(user_id, target_lang, db_path=db_path):
        return
    view = poster.AddonView(
        user_id=user_id,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
    )
    await interaction.followup.send(
        content=poster.build_addon_prompt(explanation_lang),
        view=view,
    )


async def handle_addon_request(
    interaction: discord.Interaction,
    user_id: str,
    target_lang: str,
    count: int,
    db_path: Path | None = None,
) -> None:
    """追加クイズボタン押下をハンドル: 本人検証 → 枠チェック → 消費 → 投稿。"""
    if db_path is None:
        db_path = quiz_log.DEFAULT_DB_PATH

    explanation_lang = explanation_lang_for(target_lang)
    is_ja = explanation_lang == "ja"

    if str(interaction.user.id) != user_id:
        msg = "これはあなた用のボタンじゃないよ。" if is_ja else "This isn't your button."
        await interaction.response.send_message(msg, ephemeral=True)
        return

    if quiz_log.has_used_addon_today(user_id, target_lang, db_path=db_path):
        msg = "今日はもう追加済みだよ。また明日!" if is_ja else "Already added today. See you tomorrow!"
        await interaction.response.edit_message(view=None)
        await interaction.followup.send(msg, ephemeral=True)
        return

    quiz_log.mark_addon_used(user_id, target_lang, db_path=db_path)

    if count == 0:
        msg = "了解! また明日ね。" if is_ja else "Got it! See you tomorrow."
        await interaction.response.edit_message(content=msg, view=None)
        return

    ack = (
        f"追加クイズを {count} 問用意するね…"
        if is_ja
        else f"Preparing {count} more quiz(zes)…"
    )
    await interaction.response.edit_message(content=ack, view=None)

    learner = Learner(
        discord_user_id=user_id,
        name=interaction.user.display_name,
        target_lang=target_lang,
    )

    try:
        posted = await post_addon_quizzes(interaction.channel, learner, count, db_path=db_path)
    except Exception:
        logger.exception("Addon quiz generation failed for user %s", user_id)
        posted = 0

    if posted == 0:
        # 1 問も出せなかったら枠を返却し、ボタンを復活させて再挑戦できるようにする
        # (枠を消費したまま無反応で終わる状態を避ける)。
        quiz_log.clear_addon_used(user_id, target_lang, db_path=db_path)
        retry_view = poster.AddonView(user_id, target_lang, explanation_lang)
        msg = (
            "ごめん、うまく作れなかった…。もう一度選んでみて。"
            if is_ja
            else "Sorry, I couldn't make them. Pick again."
        )
        await interaction.edit_original_response(content=msg, view=retry_view)
        return

    done = (
        f"追加クイズを {posted} 問出したよ! 下から答えてね。"
        if is_ja
        else f"Here are {posted} more quiz(zes)! Answer below."
    )
    await interaction.edit_original_response(content=done)
