import logging
import os

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BotConfig
from quiz import daily as quiz_daily
from quiz.models import Learner
from reports import weekly

logger = logging.getLogger(__name__)


def setup_weekly_scheduler(
    client: discord.Client,
    scheduler: AsyncIOScheduler,
    bot_config: BotConfig,
) -> None:
    if scheduler.running:
        return
    channel_id_str = os.getenv("REPORT_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("REPORT_CHANNEL_ID not set; weekly reports disabled")
        return
    channel_id = int(channel_id_str)
    scheduler.add_job(
        weekly.post_weekly_reports,
        CronTrigger(day_of_week="sat", hour=9, minute=0, timezone="Asia/Tokyo"),
        args=[client, channel_id, bot_config.target_lang, bot_config.learner_name],
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Weekly report scheduler started (Saturday 09:00 JST) for %s",
        bot_config.learner_name,
    )


def _get_quiz_learner(bot_config: BotConfig) -> Learner | None:
    if not bot_config.learner_discord_id:
        return None
    return Learner(
        discord_user_id=bot_config.learner_discord_id,
        name=bot_config.learner_name,
        target_lang=bot_config.target_lang,
    )


def setup_quiz_scheduler(
    client: discord.Client,
    scheduler: AsyncIOScheduler,
    bot_config: BotConfig,
) -> None:
    channel_id_str = os.getenv("QUIZ_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("QUIZ_CHANNEL_ID not set; daily quiz disabled")
        return
    learner = _get_quiz_learner(bot_config)
    if learner is None:
        logger.warning(
            "Learner Discord ID for BOT_ROLE=%s is not set; daily quiz disabled",
            bot_config.role,
        )
        return
    channel_id = int(channel_id_str)
    scheduler.add_job(
        quiz_daily.post_daily_quizzes_for_learner,
        CronTrigger(hour=8, minute=0, timezone="Asia/Tokyo"),
        args=[client, channel_id, learner],
        id="daily_quiz",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Daily quiz scheduler set (8:00 JST) for %s", learner.name)
