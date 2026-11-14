"""Local tools always available to the brain (the floor under Composio)."""

from __future__ import annotations

import json
from typing import Any, Callable

from vik808.browser_engine import BrowserEngine
from vik808.knowledge import KnowledgeBase
from vik808.skills_engine import SkillsEngine

NotifyFn = Callable[[str], None]  # sends a proactive Telegram message


def _schema(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


class LocalTools:
    """knowledge + skills + optional browser + notify, exposed as OpenAI tool schemas."""

    def __init__(
        self,
        knowledge: KnowledgeBase,
        skills: SkillsEngine,
        browser: BrowserEngine,
        notify: NotifyFn | None = None,
        knowledge_hits: int = 4,
    ):
        self.knowledge = knowledge
        self.skills = skills
        self.browser = browser
        self.notify = notify
        self.knowledge_hits = knowledge_hits

    # -------------------------------------------------------------- schemas
    def schemas(self) -> list[dict]:
        schemas = [
            _schema(
                "knowledge_search",
                "Search this repository's knowledge base (OpenAPK curated list of open source Android apps: README + categories). Returns the most relevant passages with sources.",
                {"query": {"type": "string", "description": "Search query, e.g. 'offline manga reader'"}},
                ["query"],
            ),
            _schema(
                "skill_list",
                "List installed skills (SKILL.md) available to you.",
                {},
                [],
            ),
            _schema(
                "skill_read",
                "Read the full content of an installed skill by name.",
                {"name": {"type": "string", "description": "Skill name from skill_list"}},
                ["name"],
            ),
            _schema(
                "notify_user",
                "Send a proactive notification to the user's Telegram chat (use for async job completion or important updates).",
                {"message": {"type": "string", "description": "Short notification text"}},
                ["message"],
            ),
        ]
        if self.browser.available:
            schemas.append(
                _schema(
                    "browser_open",
                    "Open a web page in the headless browser engine and return its title and visible text.",
                    {"url": {"type": "string", "description": "http(s) URL to open"}},
                    ["url"],
                )
            )
        return schemas

    # -------------------------------------------------------------- execute
    def execute(self, name: str, args: dict[str, Any]) -> str:
        try:
            return self._dispatch(name, args)
        except Exception as exc:
            return f"Tool '{name}' failed: {type(exc).__name__}: {exc}"

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "knowledge_search":
            hits = self.knowledge.format_hits(str(args.get("query", "")), k=self.knowledge_hits)
            return hits or "No matching passages found in the repository knowledge base."
        if name == "skill_list":
            return self.skills.list_for_prompt() or "No skills installed."
        if name == "skill_read":
            return self.skills.read_for_prompt(str(args.get("name", "")))
        if name == "notify_user":
            message = str(args.get("message", "")).strip() or "Viktor has an update for you."
            if self.notify:
                self.notify(message)
                return "Notification sent."
            return "Notifications are not wired up in this run."
        if name == "browser_open":
            result = self.browser.open(str(args.get("url", "")))
            return json.dumps(result, ensure_ascii=False, default=str)
        return f"Unknown tool '{name}'"
