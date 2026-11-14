"""Skills engine — Engine 2 of Vik808.

Loads SKILL.md skills (Claude/OpenClaw style), lists them for the brain, and syncs
extra skills from ClawHub sources (tarballs that contain SKILL.md files).
"""

from __future__ import annotations

import io
import re
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str

    def prompt_block(self) -> str:
        return f"### Skill: {self.name}\n{self.description}\n{self.body.strip()}"


def parse_skill(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter dict, body) from a SKILL.md document."""
    m = FRONTMATTER_RE.match(text)
    meta: dict[str, str] = {}
    body = text
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().strip('"').strip("'")
        body = text[m.end():]
    return meta, body


class SkillsEngine:
    MAX_CLAWHUB_SKILLS = 300

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}

    # ------------------------------------------------------------------ load
    def load(self) -> dict[str, Skill]:
        found: dict[str, Skill] = {}
        if self.skills_dir.is_dir():
            for skill_md in sorted(self.skills_dir.rglob("SKILL.md")):
                try:
                    text = skill_md.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                meta, body = parse_skill(text)
                name = meta.get("name") or skill_md.parent.name
                description = meta.get("description", "").strip()
                found[name] = Skill(name=name, description=description, path=skill_md, body=body)
        self._skills = found
        return found

    @property
    def skills(self) -> dict[str, Skill]:
        if not self._skills:
            self.load()
        return self._skills

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def names(self) -> list[str]:
        return sorted(self.skills)

    # --------------------------------------------------------------- prompt
    def list_for_prompt(self, limit: int = 30) -> str:
        skills = self.skills
        if not skills:
            return "(no skills installed)"
        lines = []
        for name in sorted(skills)[:limit]:
            desc = skills[name].description or "(no description)"
            lines.append(f"- {name}: {desc}")
        extra = len(skills) - limit
        if extra > 0:
            lines.append(f"- … and {extra} more (use skill_read)")
        return "\n".join(lines)

    def read_for_prompt(self, name: str) -> str:
        skill = self.get(name)
        if not skill:
            known = ", ".join(self.names()[:20])
            return f"No skill named '{name}'. Installed: {known}"
        return skill.prompt_block()

    # ------------------------------------------------------------- clawhub
    def sync_clawhub(self, sources: list[str]) -> dict:
        """Download ClawHub tarballs and extract SKILL.md files into skills/clawhub/."""
        clawhub_dir = self.skills_dir / "clawhub"
        clawhub_dir.mkdir(parents=True, exist_ok=True)
        result = {"sources": len(sources), "added": 0, "skipped": 0, "errors": []}

        for url in sources:
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    blob = resp.read()
            except Exception as exc:  # network / 404 / etc.
                result["errors"].append(f"{url}: {exc}")
                continue

            try:
                with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
                    members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith("SKILL.md")]
                    for member in members[: self.MAX_CLAWHUB_SKILLS]:
                        extracted = tar.extractfile(member)
                        if extracted is None:
                            continue
                        text = extracted.read().decode("utf-8", errors="replace")
                        meta, _ = parse_skill(text)
                        name = meta.get("name") or Path(member.name).parent.name
                        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "unnamed"
                        target_dir = clawhub_dir / safe
                        if target_dir.exists():
                            result["skipped"] += 1
                            continue
                        target_dir.mkdir(parents=True, exist_ok=True)
                        (target_dir / "SKILL.md").write_text(text, encoding="utf-8")
                        result["added"] += 1
            except tarfile.TarError as exc:
                result["errors"].append(f"{url}: not a tarball ({exc})")

        self.load()
        return result
