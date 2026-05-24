import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import logging
import os

import discord
from dotenv import load_dotenv

from reports import weekly

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id_str = os.getenv("REPORT_CHANNEL_ID")

    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set in .env")
    if not channel_id_str:
        raise RuntimeError("REPORT_CHANNEL_ID is not set in .env")

    channel_id = int(channel_id_str)
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"Logged in as {client.user}")
        try:
            await weekly.post_weekly_reports(client, channel_id)
            logger.info("Weekly report posted")
        except Exception:
            logger.exception("Failed to post weekly report")
        finally:
            await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
