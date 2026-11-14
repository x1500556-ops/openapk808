"""Vik808 — an AI coworker (Viktor) that lives in this repository.

Architecture: two engines + one brain.
  * Engine 1 — Chat engine (sessions, memory, tool loop)
  * Engine 2 — Skills engine (SKILL.md skills, ClawHub sync, GPT plugins)
  * One brain — a single OpenAI-compatible LLM
  * Optional   — browser engine (Playwright, off by default)
  * Backend    — Composio (real SDK when key present) + local tools
  * Surface    — Telegram (onboarding, chat, attachments, voice, notifications)
"""

__version__ = "0.1.0"
