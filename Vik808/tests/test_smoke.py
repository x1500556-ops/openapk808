"""Smoke tests for Vik808 — run without network, keys, or Telegram tokens."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VIK808_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = VIK808_DIR.parent
sys.path.insert(0, str(VIK808_DIR))

from config import Config  # noqa: E402


@pytest.fixture()
def cfg(tmp_path, monkeypatch) -> Config:
    for var in (
        "VIK808_LLM_API_KEY",
        "OPENAI_API_KEY",
        "VIK808_COMPOSIO_API_KEY",
        "COMPOSIO_API_KEY",
        "VIK808_TELEGRAM_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    c = Config()
    c.data_dir = tmp_path / "data"
    c.data_dir.mkdir()
    c.skills_dir = VIK808_DIR / "skills"
    c.plugins_dir = tmp_path / "plugins"
    c.knowledge_root = REPO_ROOT
    return c


class FakeBrain:
    """Scripted brain: pops queued responses, records calls."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        if not self.replies:
            return {"content": "fallback reply", "tool_calls": []}
        return self.replies.pop(0)

    def complete_text(self, system, user):
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])[
            "content"
        ]

    def generate_plugin(self, description):
        raise NotImplementedError

    def transcribe(self, path):
        return None


# --------------------------------------------------------------------- config
def test_config_defaults(cfg: Config):
    assert cfg.has_llm is False
    assert cfg.has_composio is False
    assert cfg.llm_model
    assert cfg.clawhub_source_list, "default ClawHub source expected"
    assert cfg.knowledge_root == REPO_ROOT


# ----------------------------------------------------------------- knowledge
def test_knowledge_index_and_search(cfg: Config):
    from vik808.knowledge import KnowledgeBase

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    n = kb.build()
    assert n > 20, "should chunk README + category files"
    hits = kb.search("manga reader", k=5)
    assert hits, "expected hits for 'manga reader'"
    assert all("source" in h and "text" in h for h in hits)
    # Mihon/Tachiyomi live in the README popular table
    blob = " ".join(h["text"] for h in hits).lower()
    assert "mihon" in blob or "manga" in blob
    # cache round-trip
    kb2 = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    kb2.build()
    assert len(kb2.chunks) == n


# -------------------------------------------------------------------- skills
def test_skills_engine_loads_bundled(cfg: Config):
    from vik808.skills_engine import SkillsEngine

    skills = SkillsEngine(cfg.skills_dir)
    loaded = skills.load()
    assert "openapk-catalog" in loaded
    assert "clawhub-sync" in loaded
    skill = skills.get("openapk-catalog")
    assert "knowledge_search" in skill.body
    assert "OpenAPK" in skill.description
    assert "openapk-catalog" in skills.list_for_prompt()


# -------------------------------------------------------------- tool backend
def test_backend_without_composio_falls_back(cfg: Config):
    from vik808.browser_engine import BrowserEngine
    from vik808.knowledge import KnowledgeBase
    from vik808.skills_engine import SkillsEngine
    from vik808.tools.composio_backend import ToolBackend

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    kb.build()
    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    backend = ToolBackend(cfg, kb, skills, BrowserEngine(enabled=False))
    assert backend.composio is None
    names = {s["function"]["name"] for s in backend.schemas()}
    assert {"knowledge_search", "skill_list", "skill_read", "notify_user"} <= names
    assert "browser_open" not in names  # browser disabled
    assert "not configured" in backend.status()

    out = backend.execute("knowledge_search", {"query": "encrypted messenger"})
    assert len(out) > 50
    out2 = backend.execute("skill_read", {"name": "openapk-catalog"})
    assert "OpenAPK" in out2


# ---------------------------------------------------------------- chat engine
def test_chat_engine_basic_reply(cfg: Config):
    from vik808.browser_engine import BrowserEngine
    from vik808.chat_engine import ChatEngine
    from vik808.knowledge import KnowledgeBase
    from vik808.skills_engine import SkillsEngine
    from vik808.tools.composio_backend import ToolBackend

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    kb.build()
    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    brain = FakeBrain({"content": "Hello from Viktor", "tool_calls": []})
    backend = ToolBackend(cfg, kb, skills, BrowserEngine(enabled=False))
    engine = ChatEngine(cfg, brain, backend, kb, skills)

    reply = engine.handle(1, "hi Viktor")
    assert reply == "Hello from Viktor"
    sess = engine.session(1)
    assert sess.history[-1]["role"] == "assistant"
    # persisted
    engine2 = ChatEngine(cfg, FakeBrain(), backend, kb, skills)
    assert engine2.session(1).history


def test_chat_engine_tool_loop(cfg: Config):
    from vik808.browser_engine import BrowserEngine
    from vik808.chat_engine import ChatEngine
    from vik808.knowledge import KnowledgeBase
    from vik808.skills_engine import SkillsEngine
    from vik808.tools.composio_backend import ToolBackend

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    kb.build()
    skills = SkillsEngine(cfg.skills_dir)
    skills.load()
    brain = FakeBrain(
        {
            "content": None,
            "tool_calls": [
                {"id": "t1", "name": "knowledge_search", "arguments": {"query": "manga reader"}}
            ],
        },
        {"content": "Mihon is a popular manga reader listed in the catalog.", "tool_calls": []},
    )
    backend = ToolBackend(cfg, kb, skills, BrowserEngine(enabled=False))
    engine = ChatEngine(cfg, brain, backend, kb, skills)

    reply = engine.handle(2, "any good manga readers?")
    assert "Mihon" in reply
    # second call should have carried the tool result
    assert len(brain.calls) == 2
    tool_msgs = [m for m in brain.calls[1] if m.get("role") == "tool"]
    assert tool_msgs and "mihon" in tool_msgs[0]["content"].lower()


def test_onboarding_states(cfg: Config):
    from vik808.browser_engine import BrowserEngine
    from vik808.chat_engine import ChatEngine
    from vik808.knowledge import KnowledgeBase
    from vik808.skills_engine import SkillsEngine
    from vik808.tools.composio_backend import ToolBackend

    kb = KnowledgeBase(cfg.knowledge_root, cfg.data_dir / "index.json")
    kb.build()
    skills = SkillsEngine(cfg.skills_dir)
    brain = FakeBrain({"content": "ok", "tool_calls": []})
    backend = ToolBackend(cfg, kb, skills, BrowserEngine(enabled=False))
    engine = ChatEngine(cfg, brain, backend, kb, skills)

    sess = engine.session(42)
    assert sess.state == ""
    sess.state = "awaiting_name"
    sess.name = "Kai"
    sess.state = "awaiting_workspace"
    sess.workspace = "OpenAPK"
    engine.save()
    reloaded = ChatEngine(cfg, brain, backend, kb, skills).session(42)
    assert reloaded.name == "Kai"
    assert reloaded.workspace == "OpenAPK"
    assert "Kai" in reloaded.public_summary()


# ------------------------------------------------------------------- plugins
def test_gpt_plugin_generation(cfg: Config, tmp_path):
    from vik808.plugins_gen import generate_plugin
    from vik808.skills_engine import SkillsEngine

    payload = {
        "name": "row-exporter",
        "summary": "Export OpenAPK table rows to CSV",
        "files": [
            {
                "path": "SKILL.md",
                "content": "---\nname: row-exporter\ndescription: Export table rows to CSV\n---\n# rows\n",
            },
            {"path": "exporter.py", "content": "def run(rows):\n    return ','.join(rows)\n"},
        ],
    }
    brain = FakeBrain({"content": json.dumps(payload), "tool_calls": []})
    skills = SkillsEngine(tmp_path / "skills")
    skills.load()

    result = generate_plugin(brain, skills, "export table rows", tmp_path / "plugins")
    assert result["name"] == "row-exporter"
    assert (tmp_path / "plugins" / "row-exporter" / "exporter.py").exists()
    assert (tmp_path / "plugins" / "row-exporter" / "PLUGIN.json").exists()
    assert (tmp_path / "skills" / "row-exporter" / "SKILL.md").exists()
    # registered with the skills engine
    assert "row-exporter" in skills.names()

    # path traversal must be rejected
    evil = {
        "name": "evil",
        "summary": "x",
        "files": [{"path": "../../outside.txt", "content": "nope"}],
    }
    brain2 = FakeBrain({"content": json.dumps(evil), "tool_calls": []})
    generate_plugin(brain2, skills, "evil", tmp_path / "plugins")
    assert not (tmp_path / "outside.txt").exists()


# ------------------------------------------------------------------ telegram
def test_telegram_helpers(cfg: Config):
    from vik808.telegram_bot import Notifier, _chunk

    long_text = "para one\n\n" + ("x" * 5000) + "\n\nend"
    parts = _chunk(long_text, size=3900)
    assert all(len(p) <= 3900 for p in parts)
    assert "".join(parts).replace("\n", "") == long_text.replace("\n", "")

    n = Notifier()
    n.subscribe(7)
    n.push("done")
    assert n.q.get_nowait() == ("7", "done")
    n.unsubscribe(7)
    n.push("nobody")
    assert n.q.empty()


# ---------------------------------------------------------------- brain parse
def test_plugin_json_parser():
    from vik808.brain import _parse_plugin_json

    raw = 'Sure!\n```json\n{"name":"a_b","summary":"s","files":[{"path":"x.py","content":"1"}]}\n```'
    data = _parse_plugin_json(raw)
    assert data["name"] == "a_b"
    with pytest.raises(ValueError):
        _parse_plugin_json("no json here")
