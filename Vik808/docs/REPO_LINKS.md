# Linked repositories

Vik808 lives inside **[openapk808](https://github.com/x1500556-ops/openapk808)** (its
knowledge base) and is designed to sit alongside the rest of the x1500556-ops stack.

| Repo | How Vik808 relates |
| :--- | :--- |
| [openapk808](https://github.com/x1500556-ops/openapk808) | **Home repo & knowledge base** — README + categories are indexed by `knowledge_search`; this sub-project lives at `Vik808/` |
| [copilot-X](https://github.com/x1500556-ops/copilot-X) | Open-source AI coworkers with their own browser, files & tools — the closest sibling; Vik808 brings the coworker to Telegram, copilot-X gives it a full computer |
| [xksh-muse-808](https://github.com/x1500556-ops/xksh-muse-808) | Personal agent with browser, terminal & files (CopilotKit/AG-UI) — same agent patterns, long-running work; Vik808's optional browser engine mirrors its browsing capability |
| [awesome-openclaw-skills808](https://github.com/x1500556-ops/awesome-openclaw-skills808) | **ClawHub source** — 5,400+ OpenClaw skills; the default `VIK808_CLAWHUB_SOURCES` tarball that `/clawhub` syncs from |
| [awesome-claude-code808](https://github.com/x1500556-ops/awesome-claude-code808) | Curated Claude Code agents, skills & plugins — reference material for the plugin format Vik808's `/genplugin` produces |
| [xksh808dshAgents-](https://github.com/x1500556-ops/xksh808dshAgents-) | 100+ AI agents, agent skills and RAG apps — candidate skills to package as `SKILL.md` and install |
| [xksh808dsh-genkit](https://github.com/x1500556-ops/xksh808dsh-genkit) | Genkit agent framework — an alternative runtime if Vik808's brain/tools move off the raw OpenAI-compatible client |
| [Hoolulu-api1](https://github.com/x1500556-ops/Hoolulu-api1) | Agent skills for Sapiom paid services — can be adapted into Vik808 skills for paid-service actions |

## Linking conventions

- **Knowledge flows in** from `openapk808` (automatic via `VIK808_KNOWLEDGE_ROOT`,
  default = repo root).
- **Skills flow in** from ClawHub (`awesome-openclaw-skills808` by default) and from
  GPT-generated plugins.
- **Capability repos** (`copilot-X`, `xksh-muse-808`) share the same ideas — chat
  surface here, a full computer there; a future bridge would expose their tools to
  Viktor through the Composio/MCP layer.
