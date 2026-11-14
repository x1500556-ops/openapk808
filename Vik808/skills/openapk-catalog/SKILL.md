---
name: openapk-catalog
description: Search and cite the OpenAPK curated catalog of open source Android apps (this repository's knowledge base) — apps, categories, repos, download links.
---

# OpenAPK catalog skill

This repository is the OpenAPK curated list of awesome open source apps and games for Android.

## When to use
- The user asks for app recommendations, alternatives, or "what exists for X"
- Questions about categories (messaging, security, games, …), app repos, or download pages

## How to use
1. Call `knowledge_search` with a natural-language query (e.g. "offline rss reader", "root kernel", "encrypted messenger").
2. Each hit includes `source` (file › heading). Cite it in your answer as `README.md › Popular` or `categories/security.md`.
3. Answers should include: app name, one-line description, and the upstream repo link when present in the passage.
4. If nothing matches, say so and suggest a broader query — do not invent listings.

## Layout of the knowledge base
- `README.md` — New / Updated / Popular / Featured tables (app, description, repo, download, author)
- `categories/*.md` — one file per category (automation, messaging, security, …)
