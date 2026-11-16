# Vik808 — Simple Runthrough

Viktor is an AI coworker you talk to from your phone via Telegram. It knows the
OpenAPK catalog (this repo), can use skills, and can call connected apps.
This page walks you from zero to a working bot in ~10 minutes.

## 0. What you need

- [ ] Python 3.10+ on your machine
- [ ] An LLM API key (OpenAI or any OpenAI-compatible endpoint)
- [ ] A Telegram bot token (from [@BotFather](https://t.me/BotFather)) — only for the Telegram step

## 1. Set it up

Run these from the repo root:

```bash
cd Vik808
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and fill in at least:

```bash
VIK808_LLM_API_KEY=sk-...        # your LLM key (or OPENAI_API_KEY)
VIK808_TELEGRAM_TOKEN=123:ABC     # from @BotFather
```

## 2. Build the knowledge index

```bash
python main.py index
```

This reads the repo's README + `categories/*.md` and caches a search index in
`Vik808/data/knowledge_index.json`. Re-run with `python main.py index --rebuild`
when the catalog changes.

## 3. Test it in the terminal (no Telegram needed)

```bash
python main.py chat
```

Type a message, e.g. `any good manga readers?` — Viktor should answer using the
catalog. Type `/quit` to exit.

## 4. Run it on Telegram

```bash
python main.py bot
```

Then in Telegram: open your bot, send `/start`, give your name and workspace,
and you're in. Try `/skills`, `/knowledge manga reader`, or just chat.

## 5. Optional extras

- **Connected apps (Gmail, GitHub, Slack…):** add `VIK808_COMPOSIO_API_KEY` to `.env`.
- **Browser:** set `VIK808_BROWSER_ENABLED=1`, then `pip install playwright && playwright install chromium`.
- **More skills:** send `/clawhub` in Telegram, or run `python main.py clawhub`.
- **Generate a plugin:** `/genplugin a tool that converts OpenAPK rows to CSV`.

## 6. Quick reference

| Command | What it does |
|---|---|
| `python main.py index` | (Re)build the knowledge index |
| `python main.py chat` | Chat with Viktor in the terminal |
| `python main.py bot` | Run the Telegram bot |
| `python main.py skills` | List installed skills |
| `python main.py genplugin "…"` | Generate a plugin from a description |
| `python main.py clawhub` | Sync skills from ClawHub |

Telegram commands: `/start` `/new` `/status` `/skills` `/skill <name>`
`/knowledge <query>` `/genplugin <desc>` `/clawhub` `/browser on|off`
`/notify on|off` `/help`

## 7. If something breaks

- **"No LLM key"** → check `VIK808_LLM_API_KEY` is set in `Vik808/.env`.
- **"VIK808_TELEGRAM_TOKEN is not set"** → create a bot with @BotFather and add the token.
- **Stale answers** → re-run `python main.py index --rebuild`.
- **Run the tests:** `pip install -r requirements-dev.txt && python -m pytest tests/ -q`

## 8. Where things live

- `vik808/chat_engine.py` — sessions, memory, tool loop
- `vik808/skills_engine.py` — skills (`SKILL.md`), ClawHub sync, plugins
- `vik808/brain.py` — the one LLM behind everything
- `vik808/knowledge.py` — the catalog search index
- `vik808/telegram_bot.py` — Telegram surface (onboarding, chat, voice, files)
- `docs/ARCHITECTURE.md` — deeper design notes
