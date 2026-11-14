#!/usr/bin/env python3
"""Vik808 entrypoint.

  python main.py bot                 # Telegram bot (default)
  python main.py chat                # local CLI chat with Viktor
  python main.py index [--rebuild]   # build the repository knowledge index
  python main.py genplugin "<desc>"  # GPT-generate a plugin + SKILL.md
  python main.py skills              # list installed skills
  python main.py clawhub             # sync skills from ClawHub sources
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config


def _build_core(cfg):
    from vik808.brain import Brain
    from vik808.browser_engine import BrowserEngine
    from vik808.chat_engine import ChatEngine
    from vik808.knowledge import KnowledgeBase
    from vik808.skills_engine import SkillsEngine
    from vik808.tools.composio_backend import ToolBackend

    knowledge = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "knowledge_index.json")
    knowledge.build()
    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    browser = BrowserEngine(enabled=cfg.browser_enabled)
    brain = Brain(cfg)
    notifier = _Notifier()
    backend = ToolBackend(cfg, knowledge, skills, browser, notify=notifier.push)
    engine = ChatEngine(cfg, brain, backend, knowledge, skills)
    return engine, brain, browser, notifier


class _Notifier:
    """CLI stand-in: prints proactive notifications instead of sending Telegram messages."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def push(self, message: str) -> None:
        self.messages.append(message)
        print(f"\n[notification] {message}")


def cmd_bot(cfg) -> None:
    import logging

    from vik808.telegram_bot import Notifier, build_application

    logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    engine, brain, browser, _ = _build_core(cfg)
    notifier = Notifier()
    # rewire the backend notify to the Telegram notifier
    engine.backend.local.notify = notifier.push
    app = build_application(cfg, engine, brain, browser, notifier)
    print(f"Vik808 bot starting — brain: {cfg.llm_model} · {engine.backend.status()} · {browser.status()}")
    app.run_polling(allowed_updates=["message"])


def cmd_chat(cfg) -> None:
    engine, _, _, _ = _build_core(cfg)
    chat_id = "cli"
    print("Vik808 CLI — talk to Viktor (Ctrl-D to exit)")
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return
        if not text:
            continue
        if text in {"/quit", "/exit"}:
            print("bye")
            return
        reply = engine.handle(chat_id, text)
        print(f"\nviktor> {reply}")


def cmd_index(cfg, rebuild: bool) -> None:
    from vik808.knowledge import KnowledgeBase

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "knowledge_index.json")
    n = kb.build(force=rebuild)
    print(f"Indexed {n} chunks from {cfg.knowledge_root} → {cfg.data_dir / 'knowledge_index.json'}")
    hits = kb.search("manga reader", k=3)
    for h in hits:
        print(f"  sample hit: {h['source']} › {h['heading']}")


def cmd_genplugin(cfg, description: str) -> None:
    from vik808.brain import Brain
    from vik808.plugins_gen import generate_plugin
    from vik808.skills_engine import SkillsEngine

    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    brain = Brain(cfg)
    result = generate_plugin(brain, skills, description, cfg.plugins_dir)
    print(f"Created plugin '{result['name']}' — {result['summary']}")
    for f in result["files"]:
        print(f"  {f}")


def cmd_skills(cfg) -> None:
    from vik808.skills_engine import SkillsEngine

    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    for name in skills.names():
        print(f"- {name}: {skills.get(name).description}")


def cmd_clawhub(cfg) -> None:
    from vik808.skills_engine import SkillsEngine

    skills = SkillsEngine(cfg.skills_dir)
    result = skills.sync_clawhub(cfg.clawhub_source_list)
    print(f"added={result['added']} skipped={result['skipped']} errors={len(result['errors'])}")
    for err in result["errors"]:
        print(f"  ! {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vik808 — AI coworker on your phone")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("bot", help="run the Telegram bot")
    sub.add_parser("chat", help="local CLI chat")
    p_index = sub.add_parser("index", help="build knowledge index")
    p_index.add_argument("--rebuild", action="store_true")
    p_gen = sub.add_parser("genplugin", help="GPT-generate a plugin")
    p_gen.add_argument("description", nargs="+")
    sub.add_parser("skills", help="list skills")
    sub.add_parser("clawhub", help="sync ClawHub skills")
    args = parser.parse_args()

    cfg = load_config()
    command = args.command or "bot"
    if command == "bot":
        cmd_bot(cfg)
    elif command == "chat":
        cmd_chat(cfg)
    elif command == "index":
        cmd_index(cfg, rebuild=args.rebuild)
    elif command == "genplugin":
        cmd_genplugin(cfg, " ".join(args.description))
    elif command == "skills":
        cmd_skills(cfg)
    elif command == "clawhub":
        cmd_clawhub(cfg)


if __name__ == "__main__":
    main()
