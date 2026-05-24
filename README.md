# Language Teacher Discord Bot

A bilingual Discord bot that helps two people learning each other's languages (English ↔ Japanese) get instant in-chat explanations of words, sentences, and grammar — without leaving the conversation.

## Features

- **Word lookup** — translation, part of speech, meaning, usage notes, and two example sentences. For Japanese words containing kanji, the hiragana reading (furigana) is included in the response title (e.g. `📘 視察【しさつ】(noun / suru-verb)`).
- **Sentence explanation** — natural translation, optional literal translation, and key points.
- **Grammar explanation** — topic identification, explanation, examples, and related patterns.
- **Automatic input classification** — Gemini decides whether the user input is a word, a sentence, or a grammar question; no slash commands required.
- **Language auto-detection** — Japanese characters in the input switch the target language to Japanese (and explanation language to English), and vice versa.
- **Dictionary links** — each word response links to Cambridge Dictionary (English) or Jisho (Japanese).
- **Weekly summary report** — every Monday morning JST, a summary of the past week's queries (grouped by learner and kind) is posted to a configured channel.

## How it works

1. The bot listens for messages where it is mentioned.
2. The router calls Gemini to classify the input as `word`, `sentence`, or `grammar`.
3. The matching handler queries Gemini again with a JSON-structured prompt and returns a parsed dict.
4. The result is rendered into a Discord embed (blue for English target, red for Japanese target).
5. The query is logged to a local SQLite database for the weekly report.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/app/apikey))
- A Discord channel ID for posting weekly reports

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/IwatsukaYura/discord-bot-language-teacher.git
   cd discord-bot-language-teacher
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Create a `.env` file based on `.env.example`:

   ```bash
   cp .env.example .env
   ```

   Fill in the required values:

   | Variable             | Description                                                     |
   | -------------------- | --------------------------------------------------------------- |
   | `DISCORD_BOT_TOKEN`  | Discord bot token                                               |
   | `GEMINI_API_KEY`     | Gemini API key                                                  |
   | `REPORT_CHANNEL_ID`  | Channel ID where the weekly report will be posted               |
   | `EN_LEARNER_NAME`    | Display name of the English learner (used in the weekly report) |
   | `JA_LEARNER_NAME`    | Display name of the Japanese learner (used in the weekly report)|

4. Invite the bot to your Discord server with `Read Messages` and `Send Messages` permissions, and make sure the **Message Content Intent** is enabled in the Discord Developer Portal.

## Running

### Local

```bash
uv run python src/main.py
```

### Docker

```bash
docker compose up -d
```

The bot reads `.env` and persists its SQLite log to the `./data` volume.

## Weekly Report

The bot uses APScheduler with the `Asia/Tokyo` timezone. Every Monday at 09:00 JST, it posts a summary of the previous week's queries to the channel set by `REPORT_CHANNEL_ID`. The report groups queries by learner and by kind (word / sentence / grammar), showing each query with its result and occurrence count.

To run the report manually (useful for testing):

```bash
uv run python src/scripts/run_report.py
```

## Testing

The project uses pytest with `pytest-asyncio`:

```bash
uv run pytest
```

All tests are offline (Gemini calls are mocked via `monkeypatch`).

## Project Structure

```
src/
├── main.py                    # Discord client, event handlers, scheduler setup
├── handlers/
│   ├── router.py              # Classifies input as word/sentence/grammar
│   ├── word_handler.py        # Word lookup (includes furigana for kanji)
│   ├── sentence_handler.py    # Sentence translation and explanation
│   └── grammar_handler.py     # Grammar topic explanation
├── llm/
│   └── gemini_client.py       # Gemini API wrapper
├── db/
│   └── query_log.py           # SQLite query log + schema migration
├── reports/
│   └── weekly.py              # Weekly report aggregation and embed
└── scripts/
    └── run_report.py          # Standalone script for manual report runs

tests/                         # pytest suite (mocked Gemini)
```

## License

TBD.
