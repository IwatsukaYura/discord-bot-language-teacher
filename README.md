# Language Teacher Discord Bots

A pair of bilingual Discord bots that help two people learning each other's languages (English ↔ Japanese) get instant in-chat explanations of words, sentences, and grammar — without leaving the conversation.

Two bot identities are run from one codebase:

- **English-teacher bot** (`BOT_ROLE=en_teacher`) — for Japanese-speaking learners studying English. Always replies in Japanese.
- **Japanese-teacher bot** (`BOT_ROLE=ja_teacher`) — for English-speaking learners studying Japanese. Always replies in English, with furigana on any kanji.

The bot you mention determines who the audience is. The other bot is for the other learner.

## Features

- **Word lookup** — translation, part of speech, meaning, usage notes, and two example sentences. For Japanese headwords containing kanji, the hiragana reading (furigana) is included in the response title (e.g. `📘 視察【しさつ】(noun / suru-verb)`).
- **Reverse lookup** — submit a word/sentence in your own language, the bot picks the natural equivalent in the language you're studying and uses that as the headword (with furigana for kanji where applicable). The English-teacher bot always explains in Japanese; the Japanese-teacher bot always explains in English.
- **Sentence explanation** — natural translation, optional literal translation, and key points.
- **Grammar explanation** — topic identification, explanation, examples, and related patterns.
- **Automatic input classification** — Gemini decides whether the user input is a word, a sentence, or a grammar question; no slash commands required.
- **Dictionary links** — each word response links to Cambridge Dictionary (English-teacher bot) or Jisho (Japanese-teacher bot).
- **Daily review quiz** — every morning at 08:00 JST, each bot posts a 4-choice multiple-choice quiz on the words the learner has previously looked up (review) and one brand-new word at a similar level.
- **Weekly summary report** — every Sunday at 21:00 JST, each bot posts a summary of its learner's past-week activity.

## How it works

1. The bot listens for messages where it is mentioned.
2. The router calls Gemini to classify the input as `word`, `sentence`, or `grammar`.
3. The matching handler queries Gemini with a JSON-structured prompt and returns a parsed dict. `target_lang` and `explanation_lang` are fixed by `BOT_ROLE` (not inferred from the input).
4. The result is rendered into a Discord embed (blue for English target, red for Japanese target).
5. The query is logged to a local SQLite database, shared between both bots.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Two Discord bot tokens (one per role) — create both via the [Discord Developer Portal](https://discord.com/developers/applications)
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/app/apikey))
- Channel IDs for the quiz and weekly report

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

3. Create per-role env files based on the examples:

   ```bash
   cp .env.en.example .env.en
   cp .env.ja.example .env.ja
   ```

   Required variables in each file:

   | Variable                | Description                                                  |
   | ----------------------- | ------------------------------------------------------------ |
   | `BOT_ROLE`              | `en_teacher` or `ja_teacher`                                 |
   | `DISCORD_BOT_TOKEN`     | Discord bot token (different per role)                       |
   | `GEMINI_API_KEY`        | Gemini API key                                               |
   | `REPORT_CHANNEL_ID`     | Channel where the weekly report will be posted               |
   | `QUIZ_CHANNEL_ID`       | Channel where the daily quiz will be posted                  |
   | `EN_LEARNER_NAME`       | Display name of the English-learner persona                  |
   | `EN_LEARNER_DISCORD_ID` | Discord user ID of the English learner                       |
   | `JA_LEARNER_NAME`       | Display name of the Japanese-learner persona                 |
   | `JA_LEARNER_DISCORD_ID` | Discord user ID of the Japanese learner                      |

   Each bot reads only the learner pair that matches its `BOT_ROLE`, but both env files hold both pairs so that the other identity is consistent.

4. Invite each bot to your Discord server with `Read Messages` and `Send Messages` permissions, and enable the **Message Content Intent** on each application in the Discord Developer Portal.

## Running

### Local

Run one bot at a time:

```bash
BOT_ROLE=en_teacher uv run python src/main.py
BOT_ROLE=ja_teacher uv run python src/main.py
```

(The variables in `.env.en` / `.env.ja` are loaded by `python-dotenv` only when present as `.env`; for local runs, set `BOT_ROLE` and the other variables in your shell, or use `dotenv -f .env.en run -- ...`.)

### Docker

```bash
docker compose up -d
```

`docker-compose.yml` defines two services, `bot-en` and `bot-ja`, each pointing at its own env file (`.env.en` / `.env.ja`). Both services share the `./data` volume so the SQLite database is shared.

### Production / Development environments

The bots run on a single EC2 instance with **prod** and **dev** side-by-side:

| Environment | Branch    | EC2 path                      | Compose project | SSM prefix                |
| ----------- | --------- | ----------------------------- | --------------- | ------------------------- |
| prod        | `main`    | `/opt/language-teacher/prod/` | `lt-prod`       | `/language-teacher/prod/` |
| dev         | `develop` | `/opt/language-teacher/dev/`  | `lt-dev`        | `/language-teacher/dev/`  |

- Push to `main` → GitHub Actions deploys prod.
- Push to `develop` → GitHub Actions deploys dev.
- Either environment can also be deployed manually via the "Deploy to EC2" workflow's `workflow_dispatch` input.

`scripts/deploy.sh` takes a single argument (`prod` or `dev`), pulls the matching branch, fetches secrets from the matching SSM prefix, writes `.env.en` / `.env.ja`, and runs `docker compose up -d --build` under the matching project name.

See:
- [docs/aws-infrastructure.md](docs/aws-infrastructure.md) — system diagram and design decisions
- [docs/dev-environment-setup.md](docs/dev-environment-setup.md) — one-time setup for the dev environment
- [docs/ssm-parameter-migration.md](docs/ssm-parameter-migration.md) — SSM parameter layout and migration steps

## Weekly Report (per environment)

Each bot posts only its own learner's summary to its own `REPORT_CHANNEL_ID`. dev and prod write to different channels (often different Discord servers).

Every Sunday at 21:00 JST, each bot posts its own learner's summary to its `REPORT_CHANNEL_ID`. The report groups queries by kind (word / sentence / grammar) and shows each item with its result and occurrence count.

Manual run (specify the env file for the bot you want to run it as):

```bash
uv run python src/scripts/run_report.py
```

## Daily Quiz

Every morning at 08:00 JST, each bot posts a daily quiz to its `QUIZ_CHANNEL_ID`, mentioning its learner. The quiz includes one review item from the learner's previous lookups (excluded for 14 days after delivery) and one new word at a similar level.

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
├── config.py                  # BOT_ROLE → (target_lang, explanation_lang, dictionary URL, learner)
├── handlers/
│   ├── router.py              # Classifies input as word/sentence/grammar
│   ├── word_handler.py        # Word lookup (incl. reverse lookup + furigana)
│   ├── sentence_handler.py    # Sentence translation (incl. reverse lookup)
│   ├── grammar_handler.py     # Grammar topic explanation
│   └── quiz_handler.py        # Quiz generation (review / new)
├── llm/
│   └── gemini_client.py       # Gemini API wrapper
├── db/
│   ├── query_log.py           # SQLite query log + schema migration
│   └── quiz_log.py            # SQLite quiz log
├── quiz/
│   ├── daily.py               # Daily quiz posting & answer handling
│   └── poster.py              # Quiz embed + Discord View
├── reports/
│   └── weekly.py              # Weekly report aggregation and embed
└── scripts/
    ├── run_report.py          # Standalone script for manual report runs
    └── try_quiz.py            # Local quiz generation sanity check

tests/                         # pytest suite (mocked Gemini)
```

## License

TBD.
