"""Composio backend — real SDK when VIK808_COMPOSIO_API_KEY is set, graceful fallback otherwise.

The ToolBackend facade merges local tools with Composio actions so the brain sees
one flat tool list regardless of what is configured.
"""

from __future__ import annotations

import json
from typing import Any

from config import Config
from vik808.browser_engine import BrowserEngine
from vik808.knowledge import KnowledgeBase
from vik808.skills_engine import SkillsEngine
from vik808.tools.mock_tools import LocalTools, NotifyFn

COMPOSIO_MAX_TOOLS = 40


class ComposioAdapter:
    """Thin, defensive wrapper around composio-core (0.7.x API)."""

    def __init__(self, api_key: str, entity_id: str = "default"):
        from composio import ComposioToolSet

        self.toolset = ComposioToolSet(api_key=api_key, entity_id=entity_id)
        self._schemas: list[dict] | None = None

    # -------------------------------------------------------------- schemas
    def schemas(self) -> list[dict]:
        if self._schemas is not None:
            return self._schemas
        out: list[dict] = []
        try:
            actions = self.toolset.get_action_schemas(check_connected_accounts=False)
        except Exception:
            actions = []
        for action in actions[:COMPOSIO_MAX_TOOLS]:
            try:
                params = getattr(action, "parameters", None)
                props = dict(getattr(params, "properties", None) or {})
                required = list(getattr(params, "required", None) or [])
                # strip non-JSON-schema keys some versions attach
                props = {k: v for k, v in props.items() if isinstance(v, dict)}
                out.append(
                    {
                        "type": "function",
                        "function": {
                            "name": action.name,
                            "description": (action.description or "")[:500],
                            "parameters": {"type": "object", "properties": props, "required": required},
                        },
                    }
                )
            except Exception:
                continue
        self._schemas = out
        return out

    # -------------------------------------------------------------- execute
    def execute(self, name: str, args: dict[str, Any]) -> str:
        try:
            result = self.toolset.execute_action(action=name, params=args)
        except Exception as exc:
            return f"Composio action '{name}' failed: {type(exc).__name__}: {exc}"
        return json.dumps(result, ensure_ascii=False, default=str)[:4000]

    def status(self) -> str:
        try:
            apps = self.toolset.get_apps()
            names = sorted({a.slug if hasattr(a, "slug") else str(a) for a in apps})[:12]
            return f"composio: connected ({len(apps)} apps: {', '.join(names)})"
        except Exception as exc:
            return f"composio: configured, status unavailable ({exc.__class__.__name__})"


class ToolBackend:
    """One flat tool surface: local tools + optional Composio actions."""

    def __init__(
        self,
        cfg: Config,
        knowledge: KnowledgeBase,
        skills: SkillsEngine,
        browser: BrowserEngine,
        notify: NotifyFn | None = None,
    ):
        self.cfg = cfg
        self.local = LocalTools(knowledge, skills, browser, notify=notify, knowledge_hits=cfg.knowledge_hits)
        self.composio: ComposioAdapter | None = None
        self.composio_error: str | None = None
        if cfg.has_composio:
            try:
                self.composio = ComposioAdapter(cfg.composio_api_key, cfg.composio_entity_id)
            except Exception as exc:
                self.composio_error = f"{type(exc).__name__}: {exc}"

    def schemas(self) -> list[dict]:
        schemas = self.local.schemas()
        if self.composio is not None:
            schemas = schemas + self.composio.schemas()
        return schemas

    def execute(self, name: str, args: dict[str, Any]) -> str:
        # Local tools win on name collisions; otherwise try Composio, then local.
        local_names = {s["function"]["name"] for s in self.local.schemas()}
        if name in local_names:
            return self.local.execute(name, args)
        if self.composio is not None:
            return self.composio.execute(name, args)
        return self.local.execute(name, args)

    def status(self) -> str:
        parts = [f"local tools: {len(self.local.schemas())}"]
        if self.composio is not None:
            parts.append(self.composio.status())
        elif self.cfg.has_composio:
            parts.append(f"composio: failed to init ({self.composio_error})")
        else:
            parts.append("composio: not configured (set VIK808_COMPOSIO_API_KEY for app tools)")
        return " · ".join(parts)
