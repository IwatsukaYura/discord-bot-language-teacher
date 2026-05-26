import os
from dataclasses import dataclass
from typing import Literal

BotRole = Literal["en_teacher", "ja_teacher"]

_CAMBRIDGE_URL = "https://dictionary.cambridge.org/dictionary/english/{word}"
_JISHO_URL = "https://jisho.org/search/{word}"


@dataclass(frozen=True)
class BotConfig:
    role: BotRole
    target_lang: str
    explanation_lang: str
    dictionary_url_template: str
    learner_discord_id: str | None
    learner_name: str


def load_bot_config() -> BotConfig:
    role = os.getenv("BOT_ROLE", "").strip()
    if role == "en_teacher":
        return BotConfig(
            role="en_teacher",
            target_lang="en",
            explanation_lang="ja",
            dictionary_url_template=_CAMBRIDGE_URL,
            learner_discord_id=os.getenv("EN_LEARNER_DISCORD_ID"),
            learner_name=os.getenv("EN_LEARNER_NAME", "English learner"),
        )
    if role == "ja_teacher":
        return BotConfig(
            role="ja_teacher",
            target_lang="ja",
            explanation_lang="en",
            dictionary_url_template=_JISHO_URL,
            learner_discord_id=os.getenv("JA_LEARNER_DISCORD_ID"),
            learner_name=os.getenv("JA_LEARNER_NAME", "Japanese learner"),
        )
    raise RuntimeError(
        f"BOT_ROLE must be 'en_teacher' or 'ja_teacher', got {role!r}"
    )
