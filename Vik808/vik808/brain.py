"""The one brain: a single OpenAI-compatible LLM used by both engines."""

from __future__ import annotations

import json
import re
from typing import Any

from config import Config


class BrainNotConfigured(RuntimeError):
    """Raised when no LLM API key is available."""


class Brain:
    """Thin wrapper over an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client = None

    # ------------------------------------------------------------------ client
    @property
    def client(self):
        if self._client is None:
            if not self.cfg.has_llm:
                raise BrainNotConfigured(
                    "No LLM key. Set VIK808_LLM_API_KEY (or OPENAI_API_KEY) in Vik808/.env"
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=self.cfg.llm_api_key, base_url=self.cfg.llm_base_url)
        return self._client

    # ------------------------------------------------------------------- chat
    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        """Run one completion. Returns {'content': str|None, 'tool_calls': [...]}."""
        kwargs: dict[str, Any] = dict(model=self.cfg.llm_model, messages=messages, temperature=0.4)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        tool_calls = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": choice.content, "tool_calls": tool_calls}

    def complete_text(self, system: str, user: str) -> str:
        out = self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (out["content"] or "").strip()

    # ------------------------------------------------------------- plugin gen
    def generate_plugin(self, description: str) -> dict[str, Any]:
        """Ask the brain to author a plugin as structured JSON (GPT-created plugins)."""
        system = (
            "You are Viktor, an AI coworker. Generate a small, working Python plugin "
            "for the Vik808 plugin system. Reply with ONLY minified JSON, no prose, "
            "schema: {\"name\": \"snake_case\", \"summary\": \"one line\", "
            "\"files\": [{\"path\": \"relative.py or SKILL.md\", \"content\": \"full file text\"}]}. "
            "Include exactly one SKILL.md (YAML frontmatter with name and description) plus "
            "one or more .py files. Code must be dependency-free (stdlib only) and safe."
        )
        out = self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Plugin to create: {description}"},
            ]
        )
        raw = out["content"] or ""
        return _parse_plugin_json(raw)

    # ---------------------------------------------------------------- voice
    def transcribe(self, path: str) -> str | None:
        """Speech-to-text for Telegram voice notes, when the provider supports it."""
        if not self.cfg.has_llm:
            return None
        try:
            with open(path, "rb") as fh:
                resp = self.client.audio.transcriptions.create(model="whisper-1", file=fh)
            return getattr(resp, "text", None)
        except Exception:
            return None


def _parse_plugin_json(raw: str) -> dict[str, Any]:
    """Extract a JSON object from the model output (handles ```json fences)."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("Brain did not return JSON for the plugin")
    data = json.loads(text[start : end + 1])
    if "name" not in data or "files" not in data:
        raise ValueError("Plugin JSON missing 'name' or 'files'")
    return data
