"""GPT-created plugins: ask the brain to author a plugin, save it, register its skill."""

from __future__ import annotations

import re
from pathlib import Path

from vik808.brain import Brain
from vik808.skills_engine import SkillsEngine, parse_skill

PLUGIN_SYS = (
    "You are Viktor, an AI coworker. Create a small Python plugin for Vik808. "
    "Reply with ONLY JSON: {\"name\": \"snake_case\", \"summary\": \"one line\", "
    "\"files\": [{\"path\": \"...\", \"content\": \"...\"}]}. "
    "Always include a SKILL.md with YAML frontmatter (name, description) so the skills engine "
    "can load it, plus at least one runnable .py module. Use stdlib only. No network calls at import time."
)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_-") or "plugin"


def generate_plugin(brain: Brain, skills: SkillsEngine, description: str, plugins_dir: Path) -> dict:
    """Generate a plugin from a description; writes files and reloads skills."""
    out = brain.chat(
        [
            {"role": "system", "content": PLUGIN_SYS},
            {"role": "user", "content": description},
        ]
    )
    raw = out["content"] or ""
    data = _parse(raw)
    name = _slug(str(data.get("name", "plugin")))
    summary = str(data.get("summary", description))[:300]

    # Safety: never write outside the plugins/skills dirs
    plugin_root = (plugins_dir / name).resolve()
    skills_root = Path(skills.skills_dir).resolve() if skills else None
    written: list[str] = []
    skill_md_content: str | None = None

    for entry in data.get("files", []):
        rel = str(entry.get("path", "")).strip().lstrip("/")
        content = str(entry.get("content", ""))
        if not rel or ".." in Path(rel).parts:
            continue
        if rel.endswith("SKILL.md"):
            skill_md_content = content
            continue
        target = (plugin_root / rel).resolve()
        if plugin_root not in target.parents and target != plugin_root:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target.relative_to(plugins_root(plugins_dir))))

    # Register the skill so Engine 2 (and the brain) can use the plugin
    if skill_md_content:
        meta, _ = parse_skill(skill_md_content)
        if "name" not in meta:
            skill_md_content = f"---\nname: {name}\ndescription: {summary}\n---\n{skill_md_content}"
        skill_dir = skills_root / name if skills_root else None
        if skill_dir:
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
            written.append(f"skills/{name}/SKILL.md")

    if skills:
        skills.load()

    (plugin_root).mkdir(parents=True, exist_ok=True)
    (plugin_root / "PLUGIN.json").write_text(
        f'{{"name": "{name}", "summary": "{summary}"}}\n', encoding="utf-8"
    )
    return {"name": name, "summary": summary, "files": written}


def plugins_root(plugins_dir: Path) -> Path:
    return Path(plugins_dir).resolve()


def _parse(raw: str) -> dict:
    import json
    import re as _re

    text = raw.strip()
    fence = _re.search(r"```(?:json)?\s*(.*?)```", text, _re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("The brain did not return JSON — try a more specific description")
    data = json.loads(text[start : end + 1])
    if "files" not in data:
        raise ValueError("Plugin JSON is missing 'files'")
    return data
