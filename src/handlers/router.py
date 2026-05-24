import logging
import string

from llm import gemini_client

logger = logging.getLogger(__name__)

VALID_TYPES = {"word", "sentence", "grammar"}
DEFAULT_TYPE = "word"

_SYSTEM_PROMPT = """You are a classifier for a language learning bot.
Given user input, classify it into exactly ONE of these categories:

- "word": A single word or short phrase (1-5 tokens) the user wants to learn as vocabulary.
  Examples: "apple", "林檎", "pick up", "Are you sleeping?"
- "sentence": A complete sentence the user wants translated to the other language.
  Examples: "Could you pick me up at the station?", "彼女に会いたい"
- "grammar": A meta-question about how to use a grammatical construct or pattern.
  Often includes words like "mean", "use", "意味", "使い方", "difference between".
  Examples: "What does 〜てしまう mean?", "would have p.p.の使い方"

Respond with ONLY one word: word, sentence, or grammar. No explanation, no punctuation."""


async def classify_input(text: str) -> str:
    response = await gemini_client.generate(_SYSTEM_PROMPT, text)
    normalized = response.strip().lower().strip(string.punctuation)

    if normalized not in VALID_TYPES:
        logger.warning(
            "Unexpected classification %r for input %r, defaulting to %s",
            response, text, DEFAULT_TYPE,
        )
        return DEFAULT_TYPE

    return normalized
