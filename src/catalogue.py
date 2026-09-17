from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR


@lru_cache(maxsize=1)
def load_catalogue() -> list[dict]:
    path = DATA_DIR / "catalogue.json"
    return json.loads(path.read_text(encoding="utf-8"))


def filter_catalogue(query: str = "", family: str | None = None) -> list[dict]:
    q = (query or "").lower().strip()
    rows = load_catalogue()
    if family:
        rows = [r for r in rows if r.get("family") == family]
    if not q:
        return rows
    tokens = [t for t in q.replace("/", " ").split() if t]
    scored: list[tuple[int, dict]] = []
    for row in rows:
        blob = f"{row.get('item_no','')} {row.get('description','')} {row.get('family','')}".lower()
        score = sum(3 if t in blob else 0 for t in tokens)
        if row.get("item_no", "").lower() in q:
            score += 8
        if score:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1].get("description") or ""))
    return [r for _, r in scored]


def search_catalogue(query: str, family: str | None = None, limit: int = 8) -> list[dict]:
    return filter_catalogue(query, family)[:limit]


def families() -> list[str]:
    return sorted({str(r.get("family") or "other") for r in load_catalogue()})
