# Vik808

**Your AI coworker on your phone. Chat with Viktor and keep work moving.**

Viktor is an AI coworker for your team. This sub-project gives you Viktor on your phone —
a Telegram bot connected to the same account and workspace you already use, with **this
repository (OpenAPK) as its knowledge base** and links out to your other repos.

- Chat with Viktor about your work and pick up the threads you started on your computer
- Attach photos and files, or dictate instead of typing (voice notes → transcript)
- Get notifications when Viktor replies or finishes async work
- Ask about anything in the OpenAPK catalog — apps, categories, repos — with cited sources
- Install skills from ClawHub, or have GPT generate new plugins for you

## Architecture — 2 engines + 1 brain

```
                 Telegram (onboarding · chat · attachments · voice · notifications)
                                      │
        ┌─────────────────────────────┴──────────────────────────────┐
        │                     Chat engine (Engine 1)                  │
        │        sessions · memory · retrieval · tool loop            │
        └──────────────┬──────────────────────────────┬──────────────┘
                       │                              │
              ┌────────▼────────┐            ┌────────▼─────────┐
              │   One LLM brain │            │ Skills engine     │
              │  (OpenAI-       │            │ (Engine 2)        │
              │   compatible)   │            │ SKILL.md · ClawHub│
              └────────┬────────┘            │ · GPT plugins     │
                       │                     └────────┬──────────┘
        ┌──────────────▼──────────────────────────────▼─────────────┐
        │              Tool backend                                  │
        │   Composio (real SDK, VIK808_COMPOSIO_API_KEY)            │
        │   + local tools: knowledge_search · skill_* · notify …    │
        └──────────────┬────────────────────────────────────────────┘
                       │
        ┌──────────────▼───────────────┐   ┌─────────────────────────┐
        │ Knowledge: this repo         │   │ Browser engine (optional)│
        │ README + categories/*.md     │   │ Playwright, off by def.  │
        └──────────────────────────────┘   └─────────────────────────┘
```

- **Engine 1 — Chat engine** (`vik808/chat_engine.py`): per-chat sessions, memory,
  knowledge retrieval each turn, and a tool loop (up to `VIK808_MAX_TOOL_ROUNDS`).
- **Engine 2 — Skills engine** (`vik808/skills_engine.py`): loads `SKILL.md` skills,
  syncs ClawHub tarballs, registers GPT-generated plugins as skills.
- **One brain** (`vik808/brain.py`): a single OpenAI-compatible LLM used for chat,
  plugin generation, and voice transcription.
- **Browser engine** (optional, `vik808/browser_engine.py`): headless Playwright, off
  by default (`VIK808_BROWSER_ENABLED=1` + `playwright install chromium`).
- **Composio backend** (`vik808/tools/composio_backend.py`): real `composio-core` SDK
  when `VIK808_COMPOSIO_API_KEY` is set — connected-app actions appear in the brain's
  tool list. Without a key it degrades gracefully to local tools only.

## Quickstart

```bash
cd Vik808
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # then edit: at minimum VIK808_LLM_API_KEY + VIK808_TELEGRAM_TOKEN

python main.py index    # build the OpenAPK knowledge index
python main.py chat     # local CLI chat (no Telegram needed)
python main.py bot      # run the Telegram bot
```

### Environment (`.env`)

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `VIK808_LLM_API_KEY` | ✅ | The one brain (any OpenAI-compatible key; `OPENAI_API_KEY` also works) |
| `VIK808_TELEGRAM_TOKEN` | for `bot` | Telegram bot token from @BotFather |
| `VIK808_LLM_BASE_URL` | – | OpenAI-compatible endpoint (default `https://api.openai.com/v1`) |
| `VIK808_LLM_MODEL` | – | Model name (default `gpt-4o-mini`) |
| `VIK808_COMPOSIO_API_KEY` | – | Enables the real Composio backend + connected apps |
| `VIK808_BROWSER_ENABLED` | – | `1` turns on the optional browser engine (needs playwright) |
| `VIK808_CLAWHUB_SOURCES` | – | Comma-separated ClawHub tarball URLs (defaults to `awesome-openclaw-skills808`) |

## Telegram commands

| Command | What it does |
| :--- | :--- |
| `/start` | Onboarding: name → workspace → you're in |
| `/new` | Reset the conversation thread |
| `/status` | Profile, brain, Composio, browser, skills, knowledge status |
| `/skills` · `/skill <name>` | List / read installed skills |
| `/knowledge <query>` | Search this repo's knowledge base directly |
| `/genplugin <description>` | GPT generates a plugin + registers its SKILL.md |
| `/clawhub` | Sync skills from ClawHub sources |
| `/browser on\|off` | Toggle the optional browser engine |
| `/notify on\|off` | Proactive notifications from Viktor |
| `/help` | Command list |

Photos, documents, and voice notes work in any chat with Viktor — voice notes are
transcribed (when the brain's provider supports it) and fed into the conversation.

## Commands (CLI)

```bash
python main.py bot              # Telegram bot (default)
python main.py chat             # local CLI chat
python main.py index [--rebuild]
python main.py genplugin "<description>"
python main.py skills
python main.py clawhub
```

## Repo knowledge

`vik808/knowledge.py` chunks `README.md` + `categories/*.md` from the repository root
and builds a TF-IDF index (pure Python, cached in `data/knowledge_index.json`).
Every answer that touches the catalog cites `file › heading`.

## Skills & plugins

- Skills live in `skills/<name>/SKILL.md` (YAML frontmatter: `name`, `description`).
- Bundled: `openapk-catalog`, `clawhub-sync`.
- ClawHub sync installs skills from tarballs into `skills/clawhub/`.
- `/genplugin` writes code into `plugins/<name>/` and registers `skills/<name>/SKILL.md`.

## Docs

- [Architecture](docs/ARCHITECTURE.md) — components, data flow, tool loop
- [Linked repos](docs/REPO_LINKS.md) — how Vik808 connects to your other repositories

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```
