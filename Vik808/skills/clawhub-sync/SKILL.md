---
name: clawhub-sync
description: Install additional skills from ClawHub (OpenClaw skill collections) into Vik808's skills engine.
---

# ClawHub sync skill

ClawHub is the registry of OpenClaw skills. Vik808 pulls SKILL.md files from tarball
sources and installs them under `skills/clawhub/<name>/`.

## When to use
- The user asks to "install skills from ClawHub", "sync skills", or "add more skills"

## How to use
1. Run `/clawhub` in Telegram, or `python main.py clawhub` from the CLI.
2. Sources come from `VIK808_CLAWHUB_SOURCES` (comma-separated tarball URLs).
   Default source: the `awesome-openclaw-skills808` collection (5,400+ OpenClaw skills).
3. The sync extracts up to 300 `SKILL.md` files per run, skips names already present,
   and reloads the skills engine so new skills are immediately available to the brain.

## Adding your own source
Append any `.tar.gz` URL containing `SKILL.md` files:

```
VIK808_CLAWHUB_SOURCES=https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main,https://...
```
