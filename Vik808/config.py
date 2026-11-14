"""Central configuration for Vik808 — read from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional, keeps config importable without python-dotenv
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# Vik808/ directory (this file lives at Vik808/config.py)
BASE_DIR = Path(__file__).resolve().parent
# Repository root — the OpenAPK knowledge source
REPO_ROOT = BASE_DIR.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass
class Config:
    # --- Telegram (onboarding + chat surface) ---
    telegram_token: str = field(default_factory=lambda: os.environ.get("VIK808_TELEGRAM_TOKEN", ""))

    # --- One brain: any OpenAI-compatible endpoint (GPT, local, etc.) ---
    llm_api_key: str = field(default_factory=lambda: os.environ.get("VIK808_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.environ.get("VIK808_LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.environ.get("VIK808_LLM_MODEL", "gpt-4o-mini"))

    # --- Composio backend (real SDK when key present, local fallback otherwise) ---
    composio_api_key: str = field(default_factory=lambda: os.environ.get("VIK808_COMPOSIO_API_KEY") or os.environ.get("COMPOSIO_API_KEY", ""))
    composio_entity_id: str = field(default_factory=lambda: os.environ.get("VIK808_COMPOSIO_ENTITY_ID", "default"))

    # --- Optional browser engine (playwright) ---
    browser_enabled: bool = field(default_factory=lambda: _env_bool("VIK808_BROWSER_ENABLED", False))

    # --- ClawHub skill sources (tarball URLs containing SKILL.md files) ---
    clawhub_sources: str = field(
        default_factory=lambda: os.environ.get(
            "VIK808_CLAWHUB_SOURCES",
            "https://codeload.github.com/x1500556-ops/awesome-openclaw-skills808/tar.gz/refs/heads/main",
        )
    )

    # --- Paths ---
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("VIK808_DATA_DIR", str(BASE_DIR / "data"))))
    skills_dir: Path = field(default_factory=lambda: Path(os.environ.get("VIK808_SKILLS_DIR", str(BASE_DIR / "skills"))))
    plugins_dir: Path = field(default_factory=lambda: Path(os.environ.get("VIK808_PLUGINS_DIR", str(BASE_DIR / "plugins"))))
    knowledge_root: Path = field(default_factory=lambda: Path(os.environ.get("VIK808_KNOWLEDGE_ROOT", str(REPO_ROOT))))

    # --- Behaviour ---
    history_limit: int = field(default_factory=lambda: _env_int("VIK808_HISTORY_LIMIT", 20))
    max_tool_rounds: int = field(default_factory=lambda: _env_int("VIK808_MAX_TOOL_ROUNDS", 5))
    knowledge_hits: int = field(default_factory=lambda: _env_int("VIK808_KNOWLEDGE_HITS", 4))

    @property
    def clawhub_source_list(self) -> list[str]:
        return [s.strip() for s in self.clawhub_sources.split(",") if s.strip()]

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_composio(self) -> bool:
        return bool(self.composio_api_key)


def load_config() -> Config:
    if load_dotenv is not None:
        load_dotenv(BASE_DIR / ".env")
    cfg = Config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
