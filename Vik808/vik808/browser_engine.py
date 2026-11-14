"""Optional browser engine — off by default (VIK808_BROWSER_ENABLED=1 + playwright)."""

from __future__ import annotations

import shutil
import subprocess
from urllib.parse import urlparse

MAX_TEXT = 6000


class BrowserEngine:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._pw = None

    # ----------------------------------------------------------- availability
    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import playwright  # noqa: F401

            return shutil.which("playwright") is not None or True
        except ImportError:
            return False

    def status(self) -> str:
        if not self.enabled:
            return "browser: disabled (set VIK808_BROWSER_ENABLED=1)"
        if not self.available:
            return "browser: enabled but playwright missing — pip install playwright && playwright install chromium"
        return "browser: ready"

    # ------------------------------------------------------------------ open
    def open(self, url: str) -> dict:
        if not self.available:
            return {"ok": False, "error": self.status()}
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return {"ok": False, "error": "Only http/https URLs are allowed"}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"ok": False, "error": "playwright is not installed"}

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(user_agent="Vik808/0.1 (+AI coworker)")
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                title = page.title()
                text = page.inner_text("body")[:MAX_TEXT]
                browser.close()
            return {"ok": True, "url": url, "title": title, "text": text}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
