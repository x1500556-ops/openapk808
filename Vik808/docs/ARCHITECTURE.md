# Vik808 architecture

## The shape: 2 engines + 1 brain

| Piece | Module | Role |
| :--- | :--- | :--- |
| **Engine 1 — Chat** | `vik808/chat_engine.py` | Sessions & memory, per-turn knowledge retrieval, tool loop, persona |
| **Engine 2 — Skills** | `vik808/skills_engine.py` | `SKILL.md` loading, ClawHub sync, plugin→skill registration |
| **One brain** | `vik808/brain.py` | Single OpenAI-compatible LLM: chat, plugin generation, STT |
| **Browser (optional)** | `vik808/browser_engine.py` | Headless Playwright page fetches; off unless `VIK808_BROWSER_ENABLED=1` |
| **Tool backend** | `vik808/tools/` | Composio (real SDK) merged with local tools — one flat tool list |
| **Knowledge** | `vik808/knowledge.py` | Chunks + TF-IDF index over this repo's README & categories |
| **Surface** | `vik808/telegram_bot.py` | Onboarding, chat, attachments, voice, notifications |

## Turn lifecycle

1. Telegram update arrives (text / photo / document / voice).
2. Onboarding states (`awaiting_name`, `awaiting_workspace`) intercept until complete.
3. Chat engine builds messages: system persona + profile + skill list, retrieval hits
   for this turn (`knowledge_search` pre-fetched), trimmed history, user message.
4. Brain is called with the merged tool schemas (local + Composio).
5. While the brain returns tool calls, the backend executes each and feeds results
   back — up to `VIK808_MAX_TOOL_ROUNDS` rounds — then the final text is returned.
6. History is persisted to `data/sessions.json`; the reply is chunked and sent.

## Tool surface

**Local (always on):** `knowledge_search`, `skill_list`, `skill_read`, `notify_user`,
and `browser_open` only when the browser engine is available.

**Composio (when `VIK808_COMPOSIO_API_KEY` is set):** connected-app actions (GitHub,
Gmail, Slack, …) are fetched via `ComposioToolSet.get_action_schemas()` (capped at 40)
and executed via `execute_action()`. If the SDK or key fails, the bot logs the reason
and continues with local tools — Viktor never dies because Composio is down.

## Notifications

`notify_user` (and CLI print) push through a thread-safe queue drained by an async
task started in `post_init`. Chats subscribed via `/notify on` receive proactive
messages when async work (plugin generation, long tool runs) completes.

## Data & files

```
Vik808/data/            # gitignored — sessions, knowledge index, attachments
Vik808/skills/          # SKILL.md skills (bundled + clawhub/)
Vik808/plugins/         # GPT-generated plugins
Vik808/.env             # gitignored — tokens & keys
```

## Security notes

- Generated plugins are constrained to the `plugins/` + `skills/` trees (path traversal
  is rejected) and prompted to be stdlib-only — still review before running.
- `read_file`-style tools are not exposed to the brain; knowledge retrieval is the only
  repo access, so the bot cannot read `.env` or `data/` secrets.
- Browser engine allows `http(s)` URLs only.
