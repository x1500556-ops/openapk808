"""Knowledge engine: uses this repository (OpenAPK README + categories) as its brain food.

Pure-Python retrieval — no external services. Chunks the markdown, builds a small
TF-IDF index cached under data/, and answers queries with the most relevant chunks.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "it", "this", "that", "by", "from", "as", "at", "be", "was", "were", "your", "you",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class KnowledgeBase:
    def __init__(self, root: Path, cache_path: Path):
        self.root = Path(root)
        self.cache_path = Path(cache_path)
        self.chunks: list[dict] = []
        self.doc_freq: Counter = Counter()
        self.n_docs = 0

    # ----------------------------------------------------------------- build
    def _sources(self) -> list[Path]:
        files: list[Path] = []
        readme = self.root / "README.md"
        if readme.exists():
            files.append(readme)
        cats = self.root / "categories"
        if cats.is_dir():
            files.extend(sorted(cats.glob("*.md")))
        for extra in sorted(self.root.glob("*.md")):
            if extra not in files and extra.name != "README.md":
                files.append(extra)
        return files

    @staticmethod
    def _chunk_text(text: str, source: str) -> list[dict]:
        chunks: list[dict] = []
        heading = ""
        buf: list[str] = []
        table_rows = 0

        def flush() -> None:
            body = "\n".join(buf).strip()
            if body:
                chunks.append({"source": source, "heading": heading, "text": body[:4000]})
            buf.clear()

        for line in text.splitlines():
            if line.startswith("#"):
                flush()
                heading = line.lstrip("# ").strip()
                continue
            if line.startswith("|"):
                buf.append(line)
                table_rows += 1
                if table_rows >= 25:  # split the very large README tables
                    flush()
                    table_rows = 0
                continue
            if not line.strip():
                if buf and table_rows == 0 and sum(len(x) for x in buf) > 1500:
                    flush()
                continue
            if table_rows and not line.startswith("|"):
                flush()
                table_rows = 0
            buf.append(line)
        flush()
        return chunks

    def build(self, force: bool = False) -> int:
        """(Re)build the index; uses cache when sources are unchanged."""
        stamp = self._stamp()
        if not force and self.cache_path.exists():
            try:
                cached = json.loads(self.cache_path.read_text())
                if cached.get("stamp") == stamp:
                    self._load_cached(cached)
                    return len(self.chunks)
            except (json.JSONDecodeError, KeyError):
                pass

        self.chunks = []
        for path in self._sources():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(path.relative_to(self.root))
            self.chunks.extend(self._chunk_text(text, rel))

        self.doc_freq = Counter()
        for ch in self.chunks:
            self.doc_freq.update(set(_tokenize(ch["text"])))
        self.n_docs = max(len(self.chunks), 1)
        self._save(stamp)
        return len(self.chunks)

    def _stamp(self) -> str:
        parts = []
        for path in self._sources():
            try:
                st = path.stat()
                parts.append(f"{path}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(f"{path}:gone")
        return "|".join(parts)

    def _load_cached(self, cached: dict) -> None:
        self.chunks = cached["chunks"]
        self.doc_freq = Counter(cached["doc_freq"])
        self.n_docs = cached.get("n_docs", max(len(self.chunks), 1))

    def _save(self, stamp: str) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {"stamp": stamp, "chunks": self.chunks, "doc_freq": dict(self.doc_freq), "n_docs": self.n_docs}
            ),
            encoding="utf-8",
        )

    # ---------------------------------------------------------------- search
    def search(self, query: str, k: int = 4) -> list[dict]:
        if not self.chunks:
            self.build()
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        q_counts = Counter(q_tokens)
        n_terms = len(q_counts)
        scored: list[tuple[float, dict]] = []
        for ch in self.chunks:
            d_counts = Counter(_tokenize(ch["text"]))
            score = 0.0
            present = 0
            for tok, qf in q_counts.items():
                if tok not in d_counts:
                    continue
                present += 1
                idf = math.log((self.n_docs + 1) / (self.doc_freq.get(tok, 0) + 1)) + 1.0
                # sublinear term frequency so one repeated word can't drown the query
                score += qf * (1.0 + math.log(d_counts[tok])) * idf
            if score > 0 and present:
                # reward chunks matching MORE of the query terms (e.g. "manga reader"
                # must surface rows containing both, not every "reader" row)
                score *= 1.0 + 1.5 * (present / n_terms)
                # title/heading boost so app names in headings rank higher
                if any(t in ch["heading"].lower() for t in q_tokens):
                    score *= 1.4
                scored.append((score, ch))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {"source": ch["source"], "heading": ch["heading"], "text": ch["text"]}
            for _, ch in scored[:k]
        ]

    def format_hits(self, query: str, k: int = 4) -> str:
        hits = self.search(query, k=k)
        if not hits:
            return ""
        blocks = []
        for h in hits:
            title = f"{h['source']} › {h['heading']}" if h["heading"] else h["source"]
            blocks.append(f"[{title}]\n{h['text']}")
        return "\n\n---\n\n".join(blocks)
