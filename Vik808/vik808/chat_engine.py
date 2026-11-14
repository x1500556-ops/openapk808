"""Engine 1 — Chat engine: sessions, memory, retrieval, and the tool loop."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from config import Config
from vik808.brain import Brain, BrainNotConfigured
from vik808.knowledge import KnowledgeBase
from vik808.skills_engine import SkillsEngine
from vik808.tools.composio_backend import ToolBackend

PERSONA = (
    "You are Viktor, an AI coworker for the user's team, available on their phone through Telegram. "
    "You pick up threads the user started on their computer, keep work moving, and are concise and "
    "practical. You can search this repository's knowledge (the OpenAPK curated list of open source "
    "Android apps), read and use skills, run connected-app actions through Composio, open web pages "
    "when the browser engine is on, and send the user proactive notifications. "
    "Use tools when they help; do not invent tool results. Prefer short, well-structured answers. "
    "When the user shares a file, photo, or voice transcript, work with it directly."
)


@dataclass
class Session:
    chat_id: str
    state: str = ""  # onboarding: "", "awaiting_name", "awaiting_workspace"
    name: str = ""
    workspace: str = ""
    notify_enabled: bool = True
    browser_enabled: bool = False
    history: list[dict] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def public_summary(self) -> str:
        return (
            f"user: {self.name or 'unknown'} · workspace: {self.workspace or 'none'} · "
            f"messages: {len(self.history) // 2} · notify: {'on' if self.notify_enabled else 'off'} · "
            f"browser: {'on' if self.browser_enabled else 'off'}"
        )


class ChatEngine:
    def __init__(
        self,
        cfg: Config,
        brain: Brain,
        backend: ToolBackend,
        knowledge: KnowledgeBase,
        skills: SkillsEngine,
    ):
        self.cfg = cfg
        self.brain = brain
        self.backend = backend
        self.knowledge = knowledge
        self.skills = skills
        self.sessions: dict[str, Session] = {}
        self._load_sessions()

    # ------------------------------------------------------------- sessions
    @property
    def sessions_path(self):
        return self.cfg.data_dir / "sessions.json"

    def _load_sessions(self) -> None:
        if self.sessions_path.exists():
            try:
                raw = json.loads(self.sessions_path.read_text())
                self.sessions = {k: Session(**v) for k, v in raw.items()}
            except (json.JSONDecodeError, TypeError):
                self.sessions = {}

    def save(self) -> None:
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: asdict(v) for k, v in self.sessions.items()}
        self.sessions_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def session(self, chat_id: int | str) -> Session:
        key = str(chat_id)
        if key not in self.sessions:
            self.sessions[key] = Session(chat_id=key)
        return self.sessions[key]

    def reset(self, chat_id: int | str) -> Session:
        key = str(chat_id)
        self.sessions[key] = Session(chat_id=key, name=self.sessions.get(key, Session(key)).name,
                                     workspace=self.sessions.get(key, Session(key)).workspace)
        self.save()
        return self.sessions[key]

    # ---------------------------------------------------------------- prompt
    def _system_prompt(self, sess: Session) -> str:
        context_bits = [
            PERSONA,
            "\n## Who you are talking to",
            f"- Name: {sess.name or 'not set yet'}",
            f"- Workspace: {sess.workspace or 'not set yet'}",
            "\n## Installed skills (Engine 2)",
            self.skills.list_for_prompt(),
            "\n## Knowledge retrieval",
            "Call knowledge_search before answering questions about apps, categories, or what exists "
            "in the OpenAPK repository. Cite the source (file › heading) when you use it.",
        ]
        return "\n".join(context_bits)

    def _messages(self, sess: Session, user_text: str, attachments: list[dict] | None) -> list[dict]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt(sess)}]

        # Retrieval-augmented context for this turn
        hits = self.knowledge.format_hits(user_text, k=self.cfg.knowledge_hits)
        if hits:
            messages.append(
                {"role": "system", "content": "## Relevant repository knowledge\n" + hits}
            )

        history = sess.history[-(self.cfg.history_limit * 2):]
        messages.extend(history)

        content = user_text
        if attachments:
            lines = [f"Attached {a.get('kind', 'file')}: {a.get('name', 'unknown')}"]
            if attachments[0].get("caption"):
                lines.append(f"Caption: {attachments[0]['caption']}")
            if attachments[0].get("transcript"):
                lines.append(f"Voice transcript: {attachments[0]['transcript']}")
            content = "\n".join(lines) + ("\n\n" + user_text if user_text else "")
        messages.append({"role": "user", "content": content})
        return messages

    # ---------------------------------------------------------------- handle
    def handle(self, chat_id: int | str, text: str, attachments: list[dict] | None = None) -> str:
        """One user turn → Viktor's reply (runs the tool loop)."""
        sess = self.session(chat_id)
        try:
            messages = self._messages(sess, text, attachments)
        except BrainNotConfigured as exc:
            return str(exc)

        reply_text = ""
        try:
            for _ in range(self.cfg.max_tool_rounds + 1):
                out = self.brain.chat(messages, tools=self.backend.schemas())
                if out["tool_calls"]:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": out["content"] or "",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": json.dumps(tc["arguments"]),
                                    },
                                }
                                for tc in out["tool_calls"]
                            ],
                        }
                    )
                    for tc in out["tool_calls"]:
                        result = self.backend.execute(tc["name"], tc["arguments"])
                        messages.append(
                            {"role": "tool", "tool_call_id": tc["id"], "content": str(result)[:6000]}
                        )
                    continue
                reply_text = (out["content"] or "").strip()
                break
        except BrainNotConfigured as exc:
            return str(exc)

        if not reply_text:
            reply_text = "I couldn't produce a reply — try again?"

        # persist: user turn + assistant turn (tool traffic is ephemeral)
        sess.history.append({"role": "user", "content": text or "(attachment)"})
        sess.history.append({"role": "assistant", "content": reply_text})
        sess.history = sess.history[-(self.cfg.history_limit * 2):]
        sess.updated_at = time.time()
        self.save()
        return reply_text
