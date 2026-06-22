import logging
import os

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from audio.playback import (
    handle_audio_click,
    handle_word_example_audio_click,
    parse_custom_id as parse_audio_custom_id,
    parse_word_example_custom_id,
)
from config import BotConfig, load_bot_config
from db import query_log, quiz_log
from lib.dispatcher import dispatch, extract_user_text
from lib.interaction_router import InteractionRoute, route_component_interaction
from lib.scheduler import setup_quiz_scheduler, setup_weekly_scheduler
from quiz.daily import handle_addon_request, handle_quiz_answer
from quiz.poster import parse_addon_custom_id, parse_custom_id
from reports.weekly_view import (
    handle_weekly_csv_click,
    parse_custom_id as parse_weekly_csv_custom_id,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_bot_config: BotConfig = load_bot_config()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
_scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")


@client.event
async def on_ready():
    logger.info(
        "Logged in as %s (id=%d, role=%s)",
        client.user, client.user.id, _bot_config.role,
    )
    setup_weekly_scheduler(client, _scheduler, _bot_config)
    setup_quiz_scheduler(client, _scheduler, _bot_config)


_RETRY_BUTTON_MSG = "エラーが出たみたい。少し後でもう一度ボタンを押してみて。"
_CSV_ERROR_MSG = "CSV生成でエラーが出たみたい。少し後でもう一度押してみて。"
_AUDIO_ERROR_MSG = "音声生成でエラーが出たみたい。少し後でもう一度押してみて。"

_INTERACTION_ROUTES: tuple[InteractionRoute, ...] = (
    InteractionRoute("quiz answer", parse_custom_id, handle_quiz_answer, _RETRY_BUTTON_MSG),
    InteractionRoute("addon request", parse_addon_custom_id, handle_addon_request, _RETRY_BUTTON_MSG),
    InteractionRoute("weekly CSV click", parse_weekly_csv_custom_id, handle_weekly_csv_click, _CSV_ERROR_MSG),
    InteractionRoute("audio click", parse_audio_custom_id, handle_audio_click, _AUDIO_ERROR_MSG),
    InteractionRoute(
        "word example audio click",
        parse_word_example_custom_id,
        handle_word_example_audio_click,
        _AUDIO_ERROR_MSG,
    ),
)


@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    if not interaction.data:
        return
    custom_id = interaction.data.get("custom_id", "")
    await route_component_interaction(interaction, custom_id, _INTERACTION_ROUTES)


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if client.user not in message.mentions:
        return

    user_text = extract_user_text(message.content)
    if not user_text:
        await message.channel.send("単語または文章を一緒に書いてね (例: `@Bot apple`)")
        return

    async with message.channel.typing():
        try:
            embed, view = await dispatch(
                user_text=user_text,
                user_id=str(message.author.id),
                user_name=message.author.display_name,
                bot_config=_bot_config,
            )
            send_kwargs: dict = {"embed": embed}
            if view is not None:
                send_kwargs["view"] = view
            await message.channel.send(**send_kwargs)
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
