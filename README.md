# Language Teacher Discord Bots

A pair of bilingual Discord bots that help two people learning each other's languages (English ↔ Japanese) get instant in-chat explanations of words, sentences, and grammar — without leaving the conversation.

Two bot identities are run from one codebase:

- **English-teacher bot** (`BOT_ROLE=en_teacher`) — for Japanese-speaking learners studying English. Always replies in Japanese.
- **Japanese-teacher bot** (`BOT_ROLE=ja_teacher`) — for English-speaking learners studying Japanese. Always replies in English, with furigana on any kanji.

The bot you mention determines who the audience is. The other bot is for the other learner.

## Features

- **Word lookup** — one or more senses per response. Each sense has a target-language headword, part of speech, translations, and two example sentences. The Japanese-teacher bot adds hiragana readings (furigana) to any headword containing kanji (e.g. `視察【しさつ】 (noun)`).
- **Pronunciation audio** — each word response attaches a gTTS-synthesized mp3 per unique headword, read in the target language (`en` or `ja`).
- **Reverse lookup** — submit a word/sentence in your own language, the bot picks the natural equivalent in the language you're studying and uses that as the headword (with furigana for kanji where applicable). The English-teacher bot always explains in Japanese; the Japanese-teacher bot always explains in English.
- **Sentence explanation** — natural translation, optional literal translation, and key points.
- **Grammar explanation** — topic identification, explanation, examples, and related patterns.
- **Automatic input classification** — the LLM decides whether the user input is a word, a sentence, or a grammar question; no slash commands required.
- **Dictionary links** — each word response links to Cambridge Dictionary (English-teacher bot) or Jisho (Japanese-teacher bot).
- **Model footer** — every response footer shows the actual model that answered (`via {model}`); when the OpenRouter fallback fires, the provider is shown too.
- **LLM fallback chain** — Gemini primary (`gemini-3.1-flash-lite`) → Gemini secondary (`gemini-3.5-flash`) → optional OpenRouter (configurable model). 404 / 429 / 5xx automatically fall through to the next backend.
- **Daily quiz** — every morning at 08:00 JST, each bot posts a 4-choice multiple-choice quiz: one review item from the learner's past lookups + one brand-new word at a similar level. Bonus quizzes (+1/+2/+3) can be requested once per day after answering everything.
- **Weekly report** — every Saturday at 09:00 JST, each bot posts a 7-day rolling summary with a dashboard (question count / active days / quiz accuracy) and per-kind sections.
- **Anki CSV export** — the weekly report carries a persistent button that exports that week's words as an Anki Basic CSV (Front = target-language headword with optional `【reading】`, Back = translation). Mode A / Mode B lookups are both flattened so the target language always lives on the Front side.

## How it works

1. The bot listens for messages where it is mentioned.
2. The router calls the LLM (via the fallback chain) to classify the input as `word`, `sentence`, or `grammar`.
3. The matching handler calls the LLM again with a JSON-structured prompt and parses the response. `target_lang` and `explanation_lang` are fixed by `BOT_ROLE` (not inferred from the input).
4. The result is rendered into a Discord embed (blue for English target, red for Japanese target). For `word`, a gTTS-synthesized mp3 per unique headword is attached alongside the embed.
5. The query is logged to a local SQLite database shared between both bots, with the `reading` column populated when the headword/source text contains kanji.

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Two Discord bot tokens (one per role) — create both via the [Discord Developer Portal](https://discord.com/developers/applications)
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/app/apikey))
- (Optional) An OpenRouter API key + model name for the final fallback hop ([OpenRouter](https://openrouter.ai/))
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

3. Create per-role env files from the shared example:

   ```bash
   cp .env.example .env.en   # set BOT_ROLE=en_teacher and English-teacher values
   cp .env.example .env.ja   # set BOT_ROLE=ja_teacher and Japanese-teacher values
   ```

   In `.env.en`, set `BOT_ROLE=en_teacher`, the English-teacher bot's `DISCORD_BOT_TOKEN`, and the channel IDs reserved for the English-teacher bot (`REPORT_CHANNEL_ID`, `QUIZ_CHANNEL_ID`). In `.env.ja`, set the Japanese-teacher equivalents.

   Required variables in each file:

   | Variable                | Description                                                                                       |
   | ----------------------- | ------------------------------------------------------------------------------------------------- |
   | `BOT_ROLE`              | `en_teacher` or `ja_teacher`                                                                      |
   | `DISCORD_BOT_TOKEN`     | Discord bot token (different per role)                                                            |
   | `GEMINI_API_KEY`        | Gemini API key                                                                                    |
   | `REPORT_CHANNEL_ID`     | Channel for this bot's weekly report (different per role)                                         |
   | `QUIZ_CHANNEL_ID`       | Channel for this bot's daily quiz (different per role)                                            |
   | `EN_LEARNER_NAME`       | Display name of the English-learner persona                                                       |
   | `EN_LEARNER_DISCORD_ID` | Discord user ID of the English learner                                                            |
   | `JA_LEARNER_NAME`       | Display name of the Japanese-learner persona                                                      |
   | `JA_LEARNER_DISCORD_ID` | Discord user ID of the Japanese learner                                                           |

   Optional (set both or neither — partial configuration disables the OpenRouter fallback):

   | Variable             | Description                                                                                       |
   | -------------------- | ------------------------------------------------------------------------------------------------- |
   | `OPENROUTER_API_KEY` | OpenRouter API key (used after Gemini primary + secondary are exhausted)                          |
   | `OPENROUTER_MODEL`   | OpenRouter model slug (e.g. `qwen/qwen3-next-80b-a3b-instruct:free`)                              |

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

See [docs/aws-infrastructure.md](docs/aws-infrastructure.md) for the system diagram and design decisions.

## Weekly Report (per bot, per environment)

Each bot posts only its own learner's summary to its own `REPORT_CHANNEL_ID`. The English-teacher bot and the Japanese-teacher bot write to **different channels** so the two learners' reports don't interleave. dev and prod also use different channels (often different Discord servers).

Every Saturday at 09:00 JST, each bot posts its own learner's summary to its `REPORT_CHANNEL_ID`. The window is a **rolling 7 days** (now − 7d → now), so the report always covers the week ending at the firing moment. The embed shows:

- A dashboard row: question count + per-kind breakdown / active days / quiz accuracy.
- Per-kind sections (word / sentence / grammar). Empty sections are omitted; sections over 50 items are truncated with a remainder note.
- A persistent button **📥 単語をCSVでエクスポート（Anki用）** that exports that week's words as an Anki Basic CSV (ephemeral reply). Front = the target-language headword (with `【reading】` for kanji), Back = the translation.

Manual run (specify the env file for the bot you want to run it as):

```bash
uv run python src/scripts/run_report.py
```

## Daily Quiz (per bot, per environment)

Every morning at 08:00 JST, each bot posts a daily quiz to **its own** `QUIZ_CHANNEL_ID`, mentioning its learner. The English-teacher bot posts to the English quiz channel and the Japanese-teacher bot posts to the Japanese quiz channel, so the two learners' problems don't interleave. The quiz includes one review item from the learner's previous lookups (excluded for 14 days after delivery) and one new word at a similar level.

After the learner answers everything for the day, the bot offers a one-time bonus prompt (**🔥 もっとやる? / 🔥 Want more?**) with `+1` / `+2` / `+3` / なし buttons. The chosen count of new questions is generated in a single batched LLM call. Only the learner can use the bonus, and the slot resets the next JST day.

## Testing

The project uses pytest with `pytest-asyncio`:

```bash
uv run pytest
```

All tests are offline (LLM backends and gTTS are mocked via `monkeypatch`).

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
│   └── quiz_handler.py        # Quiz generation (review / new / batch)
├── lib/
│   ├── dispatcher.py          # Routes incoming text to handlers, attaches TTS audio
│   ├── embeds.py              # Word / sentence / grammar embed builders + model footer
│   ├── scheduler.py           # APScheduler wiring (daily quiz, weekly report)
│   ├── script.py              # Language-script detection (en / ja)
│   └── tts.py                 # gTTS-based mp3 synthesis for word headwords
├── llm/
│   ├── client.py              # generate() entry + fallback chain
│   ├── errors.py              # LLMError / LLMRateLimitError
│   ├── gemini_backend.py      # Gemini backend (primary + secondary models)
│   └── openrouter_backend.py  # OpenRouter backend (optional final fallback)
├── db/
│   ├── query_log.py           # SQLite query log + reading column migration
│   └── quiz_log.py            # SQLite quiz log + addon usage table
├── quiz/
│   ├── daily.py               # Daily + bonus quiz posting and answer handling
│   └── poster.py              # Quiz embed + Discord button views
├── reports/
│   ├── weekly.py              # Weekly report aggregation + embed + Anki CSV builder
│   ├── weekly_view.py         # Persistent Anki CSV export button
│   └── anki_card.py           # query_log rows → Anki Basic Front/Back cards
└── scripts/
    ├── run_report.py          # Standalone script for manual report runs
    └── try_quiz.py            # Local quiz generation sanity check

tests/                         # pytest suite (mocked LLM backends)
```

## License

TBD.
