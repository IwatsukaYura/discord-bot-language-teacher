import logging
import os

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from config import BotConfig, load_bot_config
from db import query_log, quiz_log
from lib.dispatcher import dispatch, extract_user_text
from lib.scheduler import setup_quiz_scheduler, setup_weekly_scheduler
from quiz.daily import handle_addon_request, handle_quiz_answer
from quiz.poster import parse_addon_custom_id, parse_custom_id

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


@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    if not interaction.data:
        return
    custom_id = interaction.data.get("custom_id", "")

    parsed = parse_custom_id(custom_id)
    if parsed is not None:
        quiz_id, choice_index = parsed
        try:
            await handle_quiz_answer(interaction, quiz_id, choice_index)
        except Exception:
            logger.exception("Failed to handle quiz answer (quiz_id=%d)", quiz_id)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが出たみたい。少し後でもう一度ボタンを押してみて。",
                    ephemeral=True,
                )
        return

    addon_parsed = parse_addon_custom_id(custom_id)
    if addon_parsed is not None:
        user_id, target_lang, count = addon_parsed
        try:
            await handle_addon_request(interaction, user_id, target_lang, count)
        except Exception:
            logger.exception("Failed to handle addon request (user=%s)", user_id)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "エラーが出たみたい。少し後でもう一度ボタンを押してみて。",
                    ephemeral=True,
                )
        return


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
            embed = await dispatch(
                user_text=user_text,
                user_id=str(message.author.id),
                user_name=message.author.display_name,
                bot_config=_bot_config,
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
